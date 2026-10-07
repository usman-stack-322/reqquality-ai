from flask import request
from types import SimpleNamespace
from controllers.responses import respond

def create_controllers(services):

    def forgot_password():
        return respond(services.forgot_password(request.get_json(silent=True)))

    def reset_password():
        return respond(services.reset_password(request.get_json(silent=True)))
    return SimpleNamespace(forgot_password=forgot_password, reset_password=reset_password)
