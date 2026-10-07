from database import DATABASE_ERRORS, DATABASE_INTEGRITY_ERRORS
from functools import wraps
from flask import jsonify, request
from services.management_service import DashboardError

def create_database_action(app, get_connection):

    def database_action(view):

        @wraps(view)
        def wrapped(*args, **kwargs):
            connection = None
            try:
                connection = get_connection()
                with connection:
                    if request.method != 'GET' and connection.dialect == 'sqlite':
                        connection.execute('BEGIN IMMEDIATE')
                    return view(connection, *args, **kwargs)
            except DashboardError as error:
                return (jsonify(error=error.message), error.status)
            except DATABASE_ERRORS:
                app.logger.error('QA Manager database operation failed')
                return (jsonify(error='Unable to complete this request. Please try again.'), 503)
            finally:
                if connection:
                    connection.close()
        return wrapped
    return database_action
