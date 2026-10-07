from flask import request
from controllers.responses import respond
from services import analysis_service as service

def analyze_requirement_endpoint():
    return respond(service.analyze_requirement_endpoint(request.get_json(silent=True)))
