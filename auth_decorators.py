# auth_decorators.py
from functools import wraps
from flask import jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import User

def role_required(allowed_roles):
    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            current_user_id = get_jwt_identity()
            user = User.query.get(current_user_id)
            if not user or user.role not in allowed_roles:
                return jsonify({"error": f"Access forbidden: Requires one of {allowed_roles}"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator

# Specific role decorators for convenience
driver_required = role_required(['driver', 'both'])
rider_required = role_required(['rider', 'both'])