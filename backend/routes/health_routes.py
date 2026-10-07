from controllers import health_controller as controllers

def register_routes(app):
    app.get('/api/health')(controllers.health)
