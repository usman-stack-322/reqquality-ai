"""Compatibility import for the reorganized backend."""
import sys
from services import password_reset_service as _service
from routes.password_reset_routes import register_password_reset_routes
_service.register_password_reset_routes = register_password_reset_routes
sys.modules[__name__] = _service
