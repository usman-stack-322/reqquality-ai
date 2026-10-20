from flask import jsonify, request
from middlewares.auth import login_required, roles_required, csrf_required, api_errors
from services import case_service as service


def register_routes(app):
    @app.get('/api/requirements/<int:rid>/test-cases')
    @login_required
    def list_test_cases(rid):
        return jsonify(service.read_cases(rid))

    @app.post('/api/requirements/<int:rid>/test-cases')
    @login_required
    @roles_required('SQA Engineer')
    @csrf_required
    def create_test_case(rid):
        return jsonify(service.write_case(rid,None,request.get_json(silent=True))),201

    @app.patch('/api/requirements/<int:rid>/test-cases/<int:sid>')
    @login_required
    @roles_required('SQA Engineer')
    @csrf_required
    def edit_test_case(rid,sid):
        return jsonify(service.write_case(rid,sid,request.get_json(silent=True)))

    @app.patch('/api/requirements/<int:rid>/test-cases/<int:sid>/review')
    @login_required
    @roles_required('SQA Engineer')
    @csrf_required
    def review_test_case(rid,sid):
        return jsonify(service.review_case(rid,sid,request.get_json(silent=True)))

    @app.post('/api/requirements/<int:rid>/test-cases/<int:sid>/executions')
    @api_errors('Unable to record manual execution. Please retry with the same submission key.')
    @login_required
    @csrf_required
    def execute_test_case(rid,sid):
        service.require_execution_permission()
        return jsonify(service.record_execution(rid,sid,request.get_json(silent=True))),201

    @app.get('/api/requirements/<int:rid>/test-cases/<int:sid>/executions')
    @login_required
    def test_case_executions(rid,sid):
        return jsonify(service.read_cases(rid,sid,'executions'))

    @app.get('/api/requirements/<int:rid>/test-cases/<int:sid>/versions')
    @login_required
    def test_case_versions(rid,sid):
        return jsonify(service.read_cases(rid,sid,'versions'))
