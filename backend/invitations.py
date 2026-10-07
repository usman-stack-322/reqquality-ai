"""Compatibility import for the reorganized backend."""
import sys
from services import invitations_service as _service
from routes.invitations_routes import register_invitation_routes
_service.register_invitation_routes = register_invitation_routes
sys.modules[__name__] = _service
