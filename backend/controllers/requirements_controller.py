from flask import request
from controllers.responses import respond
from services import requirements_service as service

def create_requirement():
    return respond(service.create_requirement(request.get_json(silent=True)))

def list_requirements():
    return respond(service.list_requirements())

def get_requirement(requirement_id):
    return respond(service.get_requirement(requirement_id))

def update_review(requirement_id):
    return respond(service.update_review(requirement_id, request.get_json(silent=True)))

def update_review_status(requirement_id):
    return respond(service.update_review_status(requirement_id, request.get_json(silent=True)))

def update_reviewer_notes(requirement_id):
    return respond(service.update_reviewer_notes(requirement_id, request.get_json(silent=True)))
