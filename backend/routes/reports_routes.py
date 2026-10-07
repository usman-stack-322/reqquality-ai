from controllers import reports_controller as controllers
from middlewares.auth import login_required

def register_routes(app):
    app.get('/api/requirements/<int:requirement_id>/report.pdf')(login_required(controllers.export_requirement_pdf))
    app.get('/api/reports/project.pdf')(login_required(controllers.export_project_pdf))
    app.get('/api/exports/requirements.csv')(login_required(controllers.export_requirements_csv))
