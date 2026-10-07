from flask import Blueprint

bp = Blueprint("classes", __name__)

from app.classes import routes  # noqa: E402,F401
