from controllers.responses import respond
from services import dashboard_service as service

def dashboard_summary():
    return respond(service.dashboard_summary())
