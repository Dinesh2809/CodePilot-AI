# Proxy module that re-exports the FastAPI app from backend.app.main
from importlib import import_module

backend_main = import_module("backend.app.main")
app = getattr(backend_main, "app")
