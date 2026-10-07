from flask import Blueprint

bp = Blueprint("auth", __name__)

from app.auth import routes  # noqa: E402,F401
from app.auth.decorators import roles_required  # noqa: E402,F401
