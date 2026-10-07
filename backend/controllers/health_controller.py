from controllers.responses import respond
from services import health_service as service

def health():
    return respond(service.health())
