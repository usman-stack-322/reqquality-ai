from services.password_reset_service import create_services
from controllers.password_reset_controller import create_controllers
from middlewares.password_reset import register_response_headers

def register_password_reset_routes(app, get_connection):
    services = create_services(app, get_connection)
    controllers = create_controllers(services)
    app.post('/api/auth/forgot-password')(controllers.forgot_password)
    app.post('/api/auth/reset-password')(controllers.reset_password)
    register_response_headers(app)
