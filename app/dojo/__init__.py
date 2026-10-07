from flask import Blueprint

bp = Blueprint("dojo", __name__)

from app.dojo import routes  # noqa: E402,F401
