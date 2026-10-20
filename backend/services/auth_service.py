from time import perf_counter
import secrets
from flask import g, session
from werkzeug.security import check_password_hash, generate_password_hash
from app import LOGGER, get_connection
from middlewares.auth import _get_current_user
from services.requirement_helpers import _masked_email, _public_user
from services.responses import response_payload
from services.rate_limit_service import check_rate_limit

# Unknown/disabled users receive the same costly password check as existing users.
_DUMMY_PASSWORD_HASH = generate_password_hash(secrets.token_urlsafe(32), method='scrypt')
LOGIN_USER_QUERY = ('SELECT id, name, email, password_hash, role, created_at, is_active, auth_version, project_access '
                    'FROM users WHERE lower(email) = ?')

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
    if len(normalized_email) > 254 or len(password) > 1024:
        return response_payload(error='Email or password is too long.'), 400
    safe_email = _masked_email(normalized_email)
    LOGGER.info('login attempt normalized_email=%s', safe_email)
    started = perf_counter()
    connection = None
    timings = {'connect': 0.0, 'user_query': 0.0, 'password': 0.0, 'permissions': 0.0}
    try:
        stage = perf_counter()
        try:
            connection = get_connection()
        finally:
            # Failed acquisition used to misleadingly log connect_ms=0.
            timings['connect'] = (perf_counter() - stage) * 1000
        stage = perf_counter()
        with connection:
            limited = check_rate_limit(connection, 'login', normalized_email)
        timings['rate_limit'] = (perf_counter() - stage) * 1000
        if limited:
            return limited
        with connection.autocommit_reads():
            stage = perf_counter()
            user = connection.execute(
                LOGIN_USER_QUERY, (normalized_email,),
            ).fetchone()
            timings['user_query'] = (perf_counter() - stage) * 1000
            stage = perf_counter()
            active_user = user is not None and user['is_active']
            verified = check_password_hash(user['password_hash'] if active_user else _DUMMY_PASSWORD_HASH, password)
            timings['password'] = (perf_counter() - stage) * 1000
            if not active_user or not verified:
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
            'password_ms=%.1f permissions_ms=%.1f rate_limit_ms=%.1f tokens_ms=%.1f',
            (perf_counter() - started) * 1000, timings['connect'],
            timings['user_query'], timings['password'], timings['permissions'],
            timings.get('rate_limit', 0), timings.get('tokens', 0),
        )
    session.clear()
    return response_payload(user=public_user, csrf_token=csrf)


def current_user():
    user = _get_current_user(include_permissions=True)
    if user is None:
        from services.token_service import read_refresh_cookie
        return response_payload(authenticated=False, refresh_available=bool(read_refresh_cookie()))
    return response_payload(authenticated=True, user=g.public_current_user, csrf_token=g.access_claims['csrf'])

def logout():
    from services.token_service import logout_tokens
    return logout_tokens()


def refresh():
    from services.token_service import refresh_tokens
    return refresh_tokens()


def csrf():
    from services.token_service import csrf_token
    return csrf_token()
