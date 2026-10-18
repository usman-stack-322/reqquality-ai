from controllers import requirements_controller as controllers
from middlewares.auth import login_required, roles_required, csrf_required, api_errors

def register_routes(app):
    app.post('/api/requirements')(api_errors('Unable to save the requirement. Please try again.')(login_required(roles_required('Analyst')(csrf_required(controllers.create_requirement)))))
    app.get('/api/requirements')(login_required(controllers.list_requirements))
    app.get('/api/requirements/<int:requirement_id>')(login_required(controllers.get_requirement))
    app.patch('/api/requirements/<int:requirement_id>/review')(login_required(roles_required('SQA Engineer')(csrf_required(controllers.update_review))))
    app.patch('/api/requirements/<int:requirement_id>/review-status')(login_required(roles_required('SQA Engineer')(csrf_required(controllers.update_review_status))))
    app.patch('/api/requirements/<int:requirement_id>/reviewer-notes')(login_required(roles_required('SQA Engineer')(csrf_required(controllers.update_reviewer_notes))))

    from flask import request, jsonify, abort, g
    from services.workflow_service import change_requirement, revise_scenario
    @app.patch('/api/requirements/<int:rid>')
    @login_required
    @roles_required('Analyst')
    @csrf_required
    def edit_requirement(rid):
        return jsonify(change_requirement(rid, request.get_json(silent=True)))

    @app.post('/api/requirements/<int:rid>/submit')
    @login_required
    @roles_required('Analyst')
    @csrf_required
    def submit_requirement(rid):
        return jsonify(change_requirement(rid, request.get_json(silent=True), submit=True))

    @app.patch('/api/requirements/<int:rid>/scenarios/<int:sid>')
    @login_required
    @roles_required('SQA Engineer')
    @csrf_required
    def edit_scenario(rid, sid):
        if g.current_user['role'] != 'SQA Engineer':
            abort(403)
        return jsonify(revise_scenario(rid, sid, request.get_json(silent=True)))

    @app.patch('/api/admin/users/<int:uid>/project-access')
    @login_required
    @csrf_required
    def project_access(uid):
        if g.current_user['role'] != 'admin':
            abort(403)
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or type(data.get('enabled')) is not bool:
            abort(400)
        from app import get_connection
        from admin_dashboard import record_activity
        c = get_connection()
        try:
            with c:
                if not c.execute("SELECT 1 FROM users WHERE id=? AND role IN ('Analyst','SQA Engineer')", (uid,)).fetchone():
                    abort(404)
                c.execute('UPDATE users SET project_access=? WHERE id=?',(int(data['enabled']),uid))
                record_activity(c,g.current_user,'project_access_changed','user',uid, 'Current project access '+str(data['enabled']))
        finally:
            c.close()
        return jsonify(message='Project access updated.')

    @app.patch('/api/requirements/<int:rid>/analysis')
    @login_required
    @roles_required('Analyst')
    @csrf_required
    def accept_analysis(rid):
        if g.current_user['role'] != 'Analyst':
            abort(403)
        from services.workflow_service import save_analysis
        return jsonify(save_analysis(rid,request.get_json(silent=True)))

    @app.get('/api/requirements/<int:rid>/history/<int:hid>')
    @login_required
    def historical_requirement(rid,hid):
        import json
        from app import get_connection
        c = get_connection()
        try:
            row = c.execute('SELECT actor_id,action,created_at,snapshot FROM requirement_history WHERE id=? AND requirement_id=?',(hid,rid)).fetchone()
            if row is None:
                abort(404)
            result = dict(row)
            result['snapshot'] = json.loads(result['snapshot'])
            return jsonify(result)
        finally:
            c.close()
