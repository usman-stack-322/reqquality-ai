from time import perf_counter
import secrets
from flask import g, session
from werkzeug.security import check_password_hash
from app import LOGGER, get_connection
from middlewares.auth import _get_current_user
from services.requirement_helpers import _masked_email, _public_user
from services.responses import response_payload

def register():
    return (response_payload(error='Account creation requires an invitation from your administrator.'), 403)

def login(payload):
    data = payload
    if not isinstance(data, dict):
        LOGGER.warning('login failure normalized_email=<invalid> reason=invalid_payload')
        return (response_payload(error='Send a JSON object with your email and password.'), 400)
    email = data.get('email')
    password = data.get('password')
    if not isinstance(email, str) or not isinstance(password, str):
        LOGGER.warning('login failure normalized_email=%s reason=invalid_input', _masked_email(email))
        return (response_payload(error='Enter a valid email address and password.'), 400)
    normalized_email = email.strip().lower()
    safe_email = _masked_email(normalized_email)
    LOGGER.info('login attempt normalized_email=%s', safe_email)
    started = perf_counter()
    connection = None
    timings = {'connect': 0.0, 'user_query': 0.0, 'password': 0.0, 'permissions': 0.0}
    try:
        stage = perf_counter()
        connection = get_connection()
        timings['connect'] = (perf_counter() - stage) * 1000
        with connection.autocommit_reads():
            stage = perf_counter()
            user = connection.execute(
                'SELECT id, name, email, password_hash, role, created_at, is_active, auth_version '
                'FROM users WHERE lower(email) = ?', (normalized_email,),
            ).fetchone()
            timings['user_query'] = (perf_counter() - stage) * 1000
            if user is None or not user['is_active']:
                LOGGER.warning('login user_found=false normalized_email=%s', safe_email)
                LOGGER.warning('login password_verification=not_run reason=user_not_found')
                return (response_payload(error='Email or password is incorrect.'), 401)
            LOGGER.info('login user_found=true normalized_email=%s user_id=%s', safe_email, user['id'])
            stage = perf_counter()
            verified = check_password_hash(user['password_hash'], password)
            timings['password'] = (perf_counter() - stage) * 1000
            if not verified:
                LOGGER.warning('login password_verification=false normalized_email=%s', safe_email)
                return (response_payload(error='Email or password is incorrect.'), 401)
            LOGGER.info('login password_verification=true normalized_email=%s', safe_email)
            stage = perf_counter()
            public_user = _public_user(user, connection=connection)
            timings['permissions'] = (perf_counter() - stage) * 1000
        from services.token_service import issue_tokens
        stage = perf_counter()
        with connection:
            csrf, _ = issue_tokens(user, connection)
        timings['tokens'] = (perf_counter() - stage) * 1000
    finally:
        if connection is not None:
            connection.close()
        timings['total'] = (perf_counter() - started) * 1000
        g.login_timings = timings
        LOGGER.info(
            'login timing total_ms=%.1f connect_ms=%.1f user_query_ms=%.1f '
            'password_ms=%.1f permissions_ms=%.1f',
            (perf_counter() - started) * 1000, timings['connect'],
            timings['user_query'], timings['password'], timings['permissions'],
        )
    session.clear()
    return response_payload(user=public_user, csrf_token=csrf)


def current_user():
    user = _get_current_user()
    if user is None:
        return response_payload(authenticated=False)
    return response_payload(authenticated=True, user=_public_user(user), csrf_token=g.access_claims['csrf'])

def logout():
    from services.token_service import logout_tokens
    return logout_tokens()


def refresh():
    from services.token_service import refresh_tokens
    return refresh_tokens()


def csrf():
    from services.token_service import csrf_token
    return csrf_token()
