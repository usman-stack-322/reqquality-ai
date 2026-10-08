from functools import wraps
import hmac
from flask import g, jsonify, request, session

def get_connection():
    from app import get_connection as connect
    return connect()

def _get_current_user():
    from services.token_service import read_access_claims
    import time
    if not hasattr(g, 'current_user'):
        g.current_user = None
        claims = read_access_claims()
        if claims:
            connection = get_connection()
            try:
                with connection.autocommit_reads():
                    user = connection.execute(
                        'SELECT u.id,u.name,u.email,u.role,u.created_at,u.is_active,u.auth_version '
                        'FROM users u WHERE u.id=? AND EXISTS ('
                        'SELECT 1 FROM auth_refresh_tokens r WHERE r.user_id=u.id AND r.family_id=? '
                        'AND r.revoked_at IS NULL AND r.expires_at>?)',
                        (int(claims['sub']), claims['sid'], int(time.time())),
                    ).fetchone()
                if user and user['is_active'] and user['auth_version'] == claims['ver']:
                    g.current_user = user
                else:
                    g.clear_auth_cookies = True
            finally:
                connection.close()
    return g.current_user


def login_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):
        if _get_current_user() is None:
            return (jsonify(error='Please log in to continue.', code=getattr(g, 'access_error', 'unauthenticated')), 401)
        return view(*args, **kwargs)
    return wrapped

def roles_required(*roles):

    def decorator(view):

        @wraps(view)
        def wrapped(*args, **kwargs):
            user = _get_current_user()
            if user is None:
                return (jsonify(error='Please log in to continue.', code=getattr(g, 'access_error', 'unauthenticated')), 401)
            g.current_user = user
            allowed = user['role'] in roles
            if user['role'] != 'admin':
                from admin_dashboard import DEFAULT_PERMISSIONS
                permission = None
                if roles == ('admin',):
                    allowed = user['role'] == 'Manager'
                    if '/roles' in request.path:
                        permission = 'manage_permissions'
                    elif '/invitations' in request.path:
                        permission = 'manage_invitations'
                    elif '/users/' in request.path:
                        permission = 'manage_users'
                    elif request.path.endswith('/reviewer'):
                        permission = 'assign_reviewers'
                    elif request.path.endswith('/settings'):
                        permission = 'manage_settings'
                elif roles == ('Analyst',):
                    permission = 'create_requirements'
                elif roles == ('SQA Engineer',):
                    permission = 'review_requirements'
                if permission:
                    connection = get_connection()
                    try:
                        row = connection.execute('SELECT enabled FROM role_permissions WHERE role=? AND permission=?', (user['role'], permission)).fetchone()
                        allowed = bool(row and row['enabled'])
                    finally:
                        connection.close()
            if not allowed:
                return (jsonify(error='Your account does not have permission for this action.'), 403)
            return view(*args, **kwargs)
        return wrapped
    return decorator

def csrf_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        from services.token_service import read_access_claims, check_csrf
        claims = read_access_claims()
        if not claims or not check_csrf(claims['csrf']):
            return jsonify(error='CSRF validation failed. Obtain a fresh CSRF token.', code='csrf_failed'), 403
        return view(*args, **kwargs)
    return wrapped


def api_errors(public_message):

    def decorate(view):

        @wraps(view)
        def wrapped(*args, **kwargs):
            try:
                return view(*args, **kwargs)
            except Exception as error:
                __import__('flask').current_app.logger.exception('API endpoint failed endpoint=%s exception_type=%s', request.endpoint, type(error).__name__)
                return (jsonify(error=public_message), 500)
        return wrapped
    return decorate
