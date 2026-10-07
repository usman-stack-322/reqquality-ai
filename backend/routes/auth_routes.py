from controllers import auth_controller as controllers
from middlewares.auth import login_required, csrf_required

def register_routes(app):
    app.post('/api/auth/register')(controllers.register)
    app.post('/api/auth/login')(controllers.login)
    app.get('/api/auth/me')(controllers.current_user)
    app.post('/api/auth/logout')(login_required(csrf_required(controllers.logout)))
