from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

def kitchen_manager_required(f):
    """Ensures the authenticated user has the kitchen_manager role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if current_user.role != 'kitchen_manager':
            flash("Access denied: This module is restricted to Kitchen Managers.", "danger")
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function

def ngo_required(f):
    """Ensures the authenticated user has the ngo role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if current_user.role != 'ngo':
            flash("Access denied: This module is restricted to NGO Relief Partners.", "danger")
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function
