from controllers import dashboard_controller as controllers
from middlewares.auth import login_required, api_errors

def register_routes(app):
    app.get('/api/dashboard')(api_errors('Unable to load dashboard data. Please try again.')(login_required(controllers.dashboard_summary)))
