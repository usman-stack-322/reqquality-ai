from flask import request
from controllers.responses import respond
from services import auth_service as service

def register():
    return respond(service.register())

def login():
    return respond(service.login(request.get_json(silent=True)))

def current_user():
    return respond(service.current_user())

def logout():
    return respond(service.logout())
