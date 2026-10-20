from flask import jsonify, request
from middlewares.auth import login_required, csrf_required, api_errors
from services import bug_service as service


def register_routes(app):
    @app.get('/api/executions/<int:eid>/bugs')
    @login_required
    def execution_bugs(eid):
        return jsonify(service.read_bugs(eid=eid))

    @app.post('/api/executions/<int:eid>/bugs')
    @api_errors('Unable to save bug. Retry with the same submission key.')
    @login_required
    @csrf_required
    def report_bug(eid):
        result,status=service.create_bug(eid,request.get_json(silent=True))
        return jsonify(result),status

    @app.get('/api/bugs/<int:bid>')
    @login_required
    def get_bug(bid): return jsonify(service.read_bugs(bid=bid))

    @app.get('/api/bugs/<int:bid>/history')
    @login_required
    def bug_history(bid): return jsonify(service.read_bugs(bid=bid,events=True))

    @app.patch('/api/bugs/<int:bid>')
    @login_required
    @csrf_required
    def edit_bug(bid): return jsonify(service.edit_bug(bid,request.get_json(silent=True)))

    @app.patch('/api/bugs/<int:bid>/status')
    @login_required
    @csrf_required
    def bug_status(bid): return jsonify(service.transition(bid,request.get_json(silent=True)))
