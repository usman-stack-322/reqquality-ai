from database import DATABASE_ERRORS, DATABASE_INTEGRITY_ERRORS
from functools import wraps
from flask import jsonify, request
from services.invitations_service import InvitationError, begin_write

def create_database_action(app, get_connection):

    def database_action(view):

        @wraps(view)
        def wrapped(*args, **kwargs):
            connection = get_connection()
            try:
                with connection:
                    begin_write(connection)
                    try:
                        return view(connection, *args, **kwargs)
                    except InvitationError as error:
                        return (jsonify(error=error.message), error.code)
            except DATABASE_INTEGRITY_ERRORS:
                return (jsonify(error='An account or pending invitation already exists.'), 409)
            except DATABASE_ERRORS:
                app.logger.error('Invitation database operation failed')
                return (jsonify(error='Unable to complete this request. Please try again.'), 503)
            finally:
                connection.close()
        return wrapped
    return database_action

def register_response_headers(app):

    @app.after_request
    def invitation_privacy(response):
        if request.path.startswith('/api/invitations') or request.path.startswith('/api/admin'):
            response.headers['Cache-Control'] = 'no-store'
            response.headers['Referrer-Policy'] = 'no-referrer'
        return response
