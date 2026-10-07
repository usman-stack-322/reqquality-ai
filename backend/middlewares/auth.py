from functools import wraps
import hmac
from flask import g, jsonify, request, session

def get_connection():
    from app import get_connection as connect
    return connect()

def _get_current_user():
    if not hasattr(g, 'current_user'):
        user_id = session.get('user_id')
        if not user_id:
            g.current_user = None
        else:
            connection = get_connection()
            try:
                g.current_user = connection.execute('SELECT id, name, email, role, created_at, is_active, auth_version FROM users WHERE id = ?', (user_id,)).fetchone()
                if g.current_user is not None and (not g.current_user['is_active'] or g.current_user['auth_version'] != session.get('auth_version', 0)):
                    g.current_user = None
                    session.clear()
            finally:
                connection.close()
    return g.current_user

def login_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):
        if _get_current_user() is None:
            return (jsonify(error='Please log in to continue.'), 401)
        return view(*args, **kwargs)
    return wrapped

def roles_required(*roles):

    def decorator(view):

        @wraps(view)
        def wrapped(*args, **kwargs):
            user = _get_current_user()
            if user is None:
                return (jsonify(error='Please log in to continue.'), 401)
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
        expected = session.get('csrf_token', '')
        supplied = request.headers.get('X-CSRF-Token', '')
        if not expected or not supplied or (not hmac.compare_digest(expected, supplied)):
            return (jsonify(error='CSRF validation failed. Refresh your session and try again.'), 403)
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
