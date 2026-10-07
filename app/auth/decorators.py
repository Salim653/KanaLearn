from functools import wraps
from typing import Any, Callable

from flask import abort, current_app
from flask_login import current_user


def roles_required(*roles: str) -> Callable:
    """Ensure current_user is authenticated and has at least one of the required roles.

    Aborts with 403 if the user is authenticated but lacks the required role.
    If the user is not authenticated, triggers login_manager.unauthorized().
    """
    allowed_roles: set[str] = set()
    for role in roles:
        if isinstance(role, (list, tuple, set)):
            allowed_roles.update(role)
        else:
            allowed_roles.add(role)

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def decorated_view(*args: Any, **kwargs: Any) -> Any:
            if not current_user.is_authenticated:
                return current_app.login_manager.unauthorized()
            if current_user.role not in allowed_roles:
                abort(403)
            return fn(*args, **kwargs)

        return decorated_view

    return decorator
