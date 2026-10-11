"""Atomic database-backed fixed-window limits shared across application workers."""
import hashlib
import hmac
import time
from flask import current_app, g, request

WINDOW = 900


def initialize_rate_limit_schema(connection):
    connection.execute('''CREATE TABLE IF NOT EXISTS request_limits (
        key_hash TEXT PRIMARY KEY, window_start BIGINT NOT NULL, attempts INTEGER NOT NULL)''')
    connection.execute('CREATE INDEX IF NOT EXISTS idx_request_limits_window ON request_limits(window_start)')
    connection.commit()


def check_rate_limit(connection, kind, email=''):
    """Returns a HTTP service result when limited; never stores email/IP/token text.

    Call inside a committed transaction, including rejected attempts.
    Expired rows may be pruned out of band; counters reset on their next use.
    """
    now = int(time.time())
    window = now // WINDOW * WINDOW
    ip = request.remote_addr or 'unknown'
    if kind == 'login':
        scopes = [(ip, 100), (ip + ':' + email.strip().lower(), 10)]
    elif kind == 'forgot-password':
        scopes = [(ip, 20), (ip + ':' + email.strip().lower(), 5)]
    elif kind == 'reset-password':
        scopes = [(ip, 20)]
    elif kind == 'invitation-admin':
        scopes = [(str(g.current_user['id']), 30)]
    else:
        scopes = [(ip, 60)]
    limited = False
    for identity, maximum in scopes:
        key = hmac.new(str(current_app.config['JWT_SECRET_KEY']).encode(),
                       (kind + ':' + identity).encode(), hashlib.sha256).hexdigest()
        row = connection.execute('''INSERT INTO request_limits(key_hash,window_start,attempts)
            VALUES (?,?,1) ON CONFLICT(key_hash) DO UPDATE SET
            attempts=CASE WHEN request_limits.window_start=excluded.window_start
                THEN request_limits.attempts+1 ELSE 1 END,
            window_start=excluded.window_start RETURNING attempts''', (key, window)).fetchone()
        limited |= row['attempts'] > maximum
    if limited:
        return {'error': 'Too many attempts. Please try again later.', 'code': 'rate_limited'}, 429, {'Retry-After': str(window + WINDOW - now)}
    return None
