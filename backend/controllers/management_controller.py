from flask import request
from types import SimpleNamespace
from controllers.responses import respond

def create_controllers(services):

    def get_roles(connection):
        return respond(services.get_roles(connection))

    def update_role(connection, role):
        return respond(services.update_role(connection, role, request.get_json(silent=True)))

    def manager_dashboard(connection):
        return respond(services.manager_dashboard(connection, request.args))

    def manager_requirements(connection):
        return respond(services.manager_requirements(connection, request.args))

    def assign_reviewer(connection, requirement_id):
        return respond(services.assign_reviewer(connection, requirement_id, request.get_json(silent=True)))

    def manage_member(connection, user_id):
        return respond(services.manage_member(connection, user_id, request.get_json(silent=True)))

    def save_settings(connection):
        return respond(services.save_settings(connection, request.get_json(silent=True)))

    def change_password(connection):
        return respond(services.change_password(connection, request.get_json(silent=True)))
    return SimpleNamespace(get_roles=get_roles, update_role=update_role, manager_dashboard=manager_dashboard, manager_requirements=manager_requirements, assign_reviewer=assign_reviewer, manage_member=manage_member, save_settings=save_settings, change_password=change_password)
