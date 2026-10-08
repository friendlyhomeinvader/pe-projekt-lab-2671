from functools import wraps

from flask import abort
from flask_login import current_user

from app.models.user import User


def authenticate(username, password):
    user = User.query.filter_by(username=username).first()
    if user is None or not user.check_password(password):
        return None
    return user


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role != "ADMIN" and current_user.role not in roles:
                abort(403)
            return view_func(*args, **kwargs)

        return wrapper

    return decorator
