from services.invitations_service import create_services
from controllers.invitations_controller import create_controllers
from middlewares.invitations import create_database_action, register_response_headers

def register_invitation_routes(app, get_connection, roles_required, csrf_required):
    services = create_services(app, get_connection, roles_required, csrf_required)
    controllers = create_controllers(services)
    database_action = create_database_action(app, get_connection)
    app.get('/api/admin/invitations')(roles_required('admin')(database_action(controllers.list_invitations)))
    app.get('/api/admin/invitations/<int:invitation_id>')(roles_required('admin')(database_action(controllers.view_invitation)))
    app.post('/api/admin/invitations')(roles_required('admin')(csrf_required(database_action(controllers.create_invitation))))
    app.post('/api/admin/invitations/<int:invitation_id>/revoke')(roles_required('admin')(csrf_required(database_action(controllers.revoke_invitation))))
    app.post('/api/admin/invitations/<int:invitation_id>/resend')(roles_required('admin')(csrf_required(database_action(controllers.resend_invitation))))
    app.post('/api/invitations/validate')(database_action(controllers.validate_invitation))
    app.post('/api/invitations/verify-email')(database_action(controllers.verify_email))
    app.post('/api/invitations/accept')(database_action(controllers.accept_invitation))
    register_response_headers(app)
