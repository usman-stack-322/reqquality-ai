"""Compatibility import for the reorganized backend."""
import sys
from services import management_service as _service
from routes.management_routes import register_management_routes
_service.register_management_routes = register_management_routes
sys.modules[__name__] = _service
