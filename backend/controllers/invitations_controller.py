from flask import request
from types import SimpleNamespace
from controllers.responses import respond

def create_controllers(services):

    def list_invitations(connection):
        return respond(services.list_invitations(connection))

    def view_invitation(connection, invitation_id):
        return respond(services.view_invitation(connection, invitation_id))

    def create_invitation(connection):
        return respond(services.create_invitation(connection, request.get_json(silent=True)))

    def revoke_invitation(connection, invitation_id):
        return respond(services.revoke_invitation(connection, invitation_id))

    def resend_invitation(connection, invitation_id):
        return respond(services.resend_invitation(connection, invitation_id))

    def validate_invitation(connection):
        return respond(services.validate_invitation(connection, request.get_json(silent=True)))

    def verify_email(connection):
        return respond(services.verify_email(connection, request.get_json(silent=True)))

    def accept_invitation(connection):
        return respond(services.accept_invitation(connection, request.get_json(silent=True), request.headers))
    return SimpleNamespace(list_invitations=list_invitations, view_invitation=view_invitation, create_invitation=create_invitation, revoke_invitation=revoke_invitation, resend_invitation=resend_invitation, validate_invitation=validate_invitation, verify_email=verify_email, accept_invitation=accept_invitation)
