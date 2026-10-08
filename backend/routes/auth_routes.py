from controllers import auth_controller as controllers
from middlewares.auth import api_errors

def register_routes(app):
    app.post('/api/auth/register')(controllers.register)
    app.post('/api/auth/login')(api_errors('Unable to sign in. Please try again.')(controllers.login))
    app.get('/api/auth/me')(controllers.current_user)
    app.post('/api/auth/logout')(api_errors('Unable to log out. Please try again.')(controllers.logout))
    app.post('/api/auth/refresh')(api_errors('Unable to refresh authentication. Please sign in again.')(controllers.refresh))
    app.get('/api/auth/csrf')(api_errors('Unable to obtain a CSRF token.')(controllers.csrf))
