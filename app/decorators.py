"""Role-based access control decorators (RBAC per thesis Chapter 3)."""
from functools import wraps
from flask import abort
from flask_login import current_user


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            abort(403)
        return f(*args, **kwargs)
    return wrapper


def manager_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ("admin", "manager"):
            abort(403)
        return f(*args, **kwargs)
    return wrapper


def login_required_view(f):
    """Alias kept for readability; Flask-Login already enforces via @login_required."""
    return f
