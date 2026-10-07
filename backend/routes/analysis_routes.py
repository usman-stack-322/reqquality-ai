from controllers import analysis_controller as controllers
from middlewares.auth import login_required, roles_required, csrf_required

def register_routes(app):
    app.post('/api/analyze-requirement')(login_required(roles_required('Analyst')(csrf_required(controllers.analyze_requirement_endpoint))))
