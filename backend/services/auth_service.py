import secrets
from flask import session
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
    connection = get_connection()
    try:
        user = connection.execute('SELECT id, name, email, password_hash, role, created_at, is_active, auth_version FROM users WHERE lower(email) = ?', (normalized_email,)).fetchone()
    finally:
        connection.close()
    if user is None or not user['is_active']:
        LOGGER.warning('login user_found=false normalized_email=%s', safe_email)
        LOGGER.warning('login password_verification=not_run reason=user_not_found')
        return (response_payload(error='Email or password is incorrect.'), 401)
    LOGGER.info('login user_found=true normalized_email=%s user_id=%s', safe_email, user['id'])
    if not check_password_hash(user['password_hash'], password):
        LOGGER.warning('login password_verification=false normalized_email=%s', safe_email)
        return (response_payload(error='Email or password is incorrect.'), 401)
    LOGGER.info('login password_verification=true normalized_email=%s', safe_email)
    session.clear()
    session.permanent = True
    session['user_id'] = user['id']
    session['auth_version'] = user['auth_version']
    session['csrf_token'] = secrets.token_urlsafe(32)
    return response_payload(user=_public_user(user), csrf_token=session['csrf_token'])

def current_user():
    user = _get_current_user()
    if user is None:
        return response_payload(authenticated=False)
    return response_payload(authenticated=True, user=_public_user(user), csrf_token=session.get('csrf_token'))

def logout():
    session.clear()
    return response_payload(message='Logged out successfully.')
