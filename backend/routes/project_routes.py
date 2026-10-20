from flask import jsonify, request
from middlewares.auth import login_required, csrf_required


def register_routes(app):
    @app.route('/api/project', methods=['GET', 'PATCH'])
    @login_required
    def project():
        if request.method == 'PATCH':
            return csrf_required(write_project)()
        from app import get_connection
        from services.project_service import current_project
        c = get_connection()
        try:
            return jsonify(project=current_project(c))
        finally:
            c.close()

    def write_project():
        from app import get_connection
        from services.project_service import update_context
        c = get_connection()
        try:
            return jsonify(project=update_context(c, request.get_json(silent=True)))
        finally:
            c.close()
