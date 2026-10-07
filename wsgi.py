import os

from app import create_app

# Production/WSGI entrypoint (UB BITS Plesk / PythonAnywhere).
app = create_app(os.environ.get("FLASK_CONFIG", "production"))

# Some WSGI hosts (Plesk/Passenger, mod_wsgi) look for `application` not `app`.
application = app
