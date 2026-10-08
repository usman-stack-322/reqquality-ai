"""Signed access JWTs and rotating, hash-only persistent refresh credentials."""
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timezone
import jwt
from flask import current_app, g, request

ACCESS_COOKIE = '__Secure-reqquality_access'
REFRESH_COOKIE = '__Secure-reqquality_refresh'
ACCESS_SECONDS = 3600
REFRESH_SECONDS = 86400
ISSUER = 'reqquality-api'
AUDIENCE = 'reqquality-client'


def initialize_token_schema(connection):
    connection.execute('''CREATE TABLE IF NOT EXISTS auth_refresh_tokens (
        token_hash TEXT PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        family_id TEXT NOT NULL,
        auth_version INTEGER NOT NULL,
        created_at BIGINT NOT NULL,
        expires_at BIGINT NOT NULL,
        revoked_at BIGINT,
        replaced_by_hash TEXT)''')
    connection.execute('CREATE INDEX IF NOT EXISTS idx_auth_refresh_family ON auth_refresh_tokens(family_id)')
    connection.commit()


def _key():
    return current_app.config['JWT_SECRET_KEY']


def _hash(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def refresh_csrf(token):
    return hmac.new(str(_key()).encode(), b'refresh-csrf:' + token.encode(), hashlib.sha256).hexdigest()


def check_csrf(expected):
    supplied = request.headers.get('X-CSRF-Token', '')
    return bool(expected and supplied and hmac.compare_digest(expected.encode(), supplied.encode()))


def read_refresh_cookie():
    token = request.cookies.get(REFRESH_COOKIE, '')
    return token if 40 <= len(token) <= 128 and token.isascii() else None


def read_access_claims():
    if hasattr(g, 'access_claims'):
        return g.access_claims
    encoded = request.cookies.get(ACCESS_COOKIE)
    g.access_claims = None
    g.access_error = 'unauthenticated'
    if not encoded or len(encoded) > 4096:
        return None
    try:
        claims = jwt.decode(encoded, _key(), algorithms=['HS256'], issuer=ISSUER,
                            audience=AUDIENCE, options={'require': ['exp', 'iat', 'nbf', 'sub', 'jti', 'sid', 'ver', 'csrf', 'type']})
        if claims['type'] != 'access' or not claims['sub'].isdigit() or int(claims['sub']) < 1:
            return None
        if type(claims['ver']) is not int or not all(isinstance(claims[k], str) for k in ('sid', 'csrf', 'jti')):
            return None
        g.access_claims = claims
    except jwt.ExpiredSignatureError:
        g.access_error = 'access_token_expired'
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError, AttributeError):
        pass
    return g.access_claims


def issue_tokens(user, connection, family_id=None, refresh_expires=None):
    """Caller must enclose this write in its transaction."""
    now = int(time.time())
    token = secrets.token_urlsafe(48)
    family_id = family_id or secrets.token_urlsafe(32)
    refresh_expires = refresh_expires or now + REFRESH_SECONDS
    csrf = refresh_csrf(token)
    access_expires = min(now + ACCESS_SECONDS, refresh_expires)
    claims = {'sub': str(user['id']), 'ver': user['auth_version'], 'sid': family_id,
              'iat': now, 'nbf': now, 'exp': access_expires, 'jti': secrets.token_urlsafe(24),
              'iss': ISSUER, 'aud': AUDIENCE, 'type': 'access', 'csrf': csrf}
    access = jwt.encode(claims, _key(), algorithm='HS256')
    connection.execute('''INSERT INTO auth_refresh_tokens
        (token_hash,user_id,family_id,auth_version,created_at,expires_at)
        VALUES (?,?,?,?,?,?)''', (_hash(token), user['id'], family_id, user['auth_version'], now, refresh_expires))
    # Tokens travel only in Set-Cookie, never response JSON or session storage.
    g.auth_cookies = {'access': access, 'refresh': token, 'access_expires': access_expires,
                      'refresh_expires': refresh_expires}
    return csrf, _hash(token)


def _reject(message='Please sign in again.'):
    g.clear_auth_cookies = True
    return {'error': message, 'code': 'refresh_token_invalid'}, 401


def revoke_family(connection, family_id):
    connection.execute('UPDATE auth_refresh_tokens SET revoked_at=? WHERE family_id=? AND revoked_at IS NULL',
                       (int(time.time()), family_id))


def revoke_user_tokens(connection, user_id):
    connection.execute('UPDATE auth_refresh_tokens SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL',
                       (int(time.time()), user_id))


def _refresh_row(connection, token, lock=False):
    suffix = ' FOR UPDATE' if lock and connection.dialect == 'postgres' else ''
    return connection.execute('SELECT * FROM auth_refresh_tokens WHERE token_hash=?' + suffix, (_hash(token),)).fetchone()


def _user(connection, row):
    user = connection.execute('SELECT id,name,email,role,created_at,is_active,auth_version FROM users WHERE id=?', (row['user_id'],)).fetchone()
    return user if user and user['is_active'] and user['auth_version'] == row['auth_version'] else None


def refresh_tokens():
    from app import get_connection
    from services.requirement_helpers import _public_user
    token = read_refresh_cookie()
    if not token:
        return _reject()
    if not check_csrf(refresh_csrf(token)):
        return {'error': 'CSRF validation failed. Obtain a fresh CSRF token.', 'code': 'csrf_failed'}, 403
    connection = get_connection()
    try:
        with connection:
            if connection.dialect == 'sqlite':
                connection.execute('BEGIN IMMEDIATE')
            row = _refresh_row(connection, token, lock=True)
            if not row:
                return _reject()
            if row['revoked_at'] is not None:
                revoke_family(connection, row['family_id'])
                return _reject('Refresh token reuse detected. Please sign in again.')
            user = _user(connection, row)
            if row['expires_at'] <= int(time.time()) or not user:
                revoke_family(connection, row['family_id'])
                return _reject()
            csrf, replacement = issue_tokens(user, connection, row['family_id'], row['expires_at'])
            connection.execute('UPDATE auth_refresh_tokens SET revoked_at=?,replaced_by_hash=? WHERE token_hash=?',
                               (int(time.time()), replacement, row['token_hash']))
            return {'user': _public_user(user, connection), 'csrf_token': csrf}
    finally:
        connection.close()


def csrf_token():
    """Read-only bootstrap for a client that has lost its in-memory CSRF value."""
    from app import get_connection
    claims = read_access_claims()
    if claims:
        return {'csrf_token': claims['csrf']}
    token = read_refresh_cookie()
    if not token:
        return _reject()
    connection = get_connection()
    try:
        with connection.autocommit_reads():
            row = _refresh_row(connection, token)
            if not row or row['revoked_at'] is not None or row['expires_at'] <= int(time.time()) or not _user(connection, row):
                return _reject()
        return {'csrf_token': refresh_csrf(token)}
    finally:
        connection.close()


def logout_tokens():
    from app import get_connection
    claims = read_access_claims()
    token = read_refresh_cookie()
    expected = claims['csrf'] if claims else refresh_csrf(token) if token else None
    if not expected:
        return _reject()
    if not check_csrf(expected):
        return {'error': 'CSRF validation failed. Obtain a fresh CSRF token.', 'code': 'csrf_failed'}, 403
    connection = get_connection()
    try:
        with connection:
            family_id = claims['sid'] if claims else None
            if not family_id and token:
                row = _refresh_row(connection, token, lock=True)
                family_id = row['family_id'] if row else None
            if family_id:
                revoke_family(connection, family_id)
    finally:
        connection.close()
    g.clear_auth_cookies = True
    from flask import session
    session.clear()
    return {'message': 'Logged out successfully.'}


def apply_auth_cookies(response):
    if request.path.startswith('/api/auth/'):
        response.headers['Cache-Control'] = 'no-store'
    values = getattr(g, 'auth_cookies', None)
    if values and 200 <= response.status_code < 300:
        for name, key, path in [(ACCESS_COOKIE, 'access', '/api/'), (REFRESH_COOKIE, 'refresh', '/api/auth/')]:
            expiry = values[key + '_expires']
            response.set_cookie(name, values[key], max_age=max(0, expiry - int(time.time())),
                                expires=datetime.fromtimestamp(expiry, timezone.utc),
                                path=path, secure=True, httponly=True, samesite='Lax')
    if getattr(g, 'clear_auth_cookies', False) and response.status_code < 500:
        response.delete_cookie(ACCESS_COOKIE, path='/api/', secure=True, httponly=True, samesite='Lax')
        response.delete_cookie(REFRESH_COOKIE, path='/api/auth/', secure=True, httponly=True, samesite='Lax')
    return response
