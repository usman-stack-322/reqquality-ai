"""WSGI entry point for production servers such as Gunicorn and Vercel."""

import sys
from pathlib import Path

# Production loaders can import backend.wsgi from the repository root.
# The backend's existing imports resolve modules relative to this directory.
backend_directory = str(Path(__file__).resolve().parent)
if backend_directory not in sys.path:
    sys.path.insert(0, backend_directory)

from app import app
