from services.management_service import create_services
from controllers.management_controller import create_controllers
from middlewares.management import create_database_action

def register_management_routes(app, get_connection, roles_required, csrf_required, login_required):
    services = create_services(app, get_connection, roles_required, csrf_required, login_required)
    controllers = create_controllers(services)
    database_action = create_database_action(app, get_connection)
    app.get('/api/admin/roles')(roles_required('admin')(database_action(controllers.get_roles)))
    app.patch('/api/admin/roles/<role>')(roles_required('admin')(csrf_required(database_action(controllers.update_role))))
    app.get('/api/admin/dashboard')(roles_required('admin')(database_action(controllers.manager_dashboard)))
    app.get('/api/admin/requirements')(roles_required('admin')(database_action(controllers.manager_requirements)))
    app.patch('/api/admin/requirements/<int:requirement_id>/reviewer')(roles_required('admin')(csrf_required(database_action(controllers.assign_reviewer))))
    app.patch('/api/admin/users/<int:user_id>')(roles_required('admin')(csrf_required(database_action(controllers.manage_member))))
    app.patch('/api/admin/settings')(roles_required('admin')(csrf_required(database_action(controllers.save_settings))))
    app.post('/api/auth/change-password')(login_required(csrf_required(database_action(controllers.change_password))))
