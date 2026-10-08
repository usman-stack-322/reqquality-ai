from flask import g, make_response, request
from controllers.responses import respond
from services import auth_service as service

def register():
    return respond(service.register())

def login():
    response = make_response(respond(service.login(request.get_json(silent=True))))
    timings = getattr(g, 'login_timings', None)
    if timings is not None:
        response.headers['Server-Timing'] = ', '.join(
            f'{stage};dur={duration:.1f}' for stage, duration in timings.items()
        )
    return response

def current_user():
    return respond(service.current_user())

def logout():
    return respond(service.logout())


def refresh():
    return respond(service.refresh())


def csrf():
    return respond(service.csrf())
