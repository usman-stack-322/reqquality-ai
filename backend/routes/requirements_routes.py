from controllers import requirements_controller as controllers
from middlewares.auth import login_required, roles_required, csrf_required, api_errors

def register_routes(app):
    app.post('/api/requirements')(api_errors('Unable to save the requirement. Please try again.')(login_required(roles_required('Analyst')(csrf_required(controllers.create_requirement)))))
    app.get('/api/requirements')(login_required(controllers.list_requirements))
    app.get('/api/requirements/<int:requirement_id>')(login_required(controllers.get_requirement))
    app.patch('/api/requirements/<int:requirement_id>/review')(login_required(roles_required('SQA Engineer')(csrf_required(controllers.update_review))))
    app.patch('/api/requirements/<int:requirement_id>/review-status')(login_required(roles_required('SQA Engineer')(csrf_required(controllers.update_review_status))))
    app.patch('/api/requirements/<int:requirement_id>/reviewer-notes')(login_required(roles_required('SQA Engineer')(csrf_required(controllers.update_reviewer_notes))))
