from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user
from app import db
from app.models import User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username_or_email = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        user = User.query.filter(
            (User.username == username_or_email) | (User.email == username_or_email)
        ).first()

        if user and user.check_password(password):
            login_user(user, remember=True)
            flash(f"Welcome back, {user.organization_name}!", "success")
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard.index'))
        else:
            flash("Invalid username or password. Please try again.", "danger")

    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'kitchen_manager')
        organization_name = request.form.get('organization_name', '').strip()
        contact_phone = request.form.get('contact_phone', '').strip()
        address = request.form.get('address', '').strip()

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or Email already registered. Please login.", "warning")
            return redirect(url_for('auth.login'))

        new_user = User(
            username=username,
            email=email,
            role=role,
            organization_name=organization_name or username,
            contact_phone=contact_phone,
            address=address
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        flash("Registration successful! Welcome to the EcoPlate AI ecosystem.", "success")
        return redirect(url_for('dashboard.index'))

    return render_template('auth/register.html')

@auth_bp.route('/logout')
def logout():
    logout_user()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for('auth.login'))

@auth_bp.route('/demo-login/<role>')
def demo_login(role):
    """
    Convenient one-click persona switcher for SIH presentation / evaluation.
    Quickly login as 'kitchen_manager' or 'ngo'.
    """
    valid_roles = ['kitchen_manager', 'ngo']
    if role not in valid_roles:
        role = 'kitchen_manager'

    user = User.query.filter_by(role=role).first()
    if not user:
        # Fallback if seed not run yet
        user = User(
            username=f"demo_{role}",
            email=f"demo_{role}@ecoplate.org",
            role=role,
            organization_name="Apex University Central Cafeteria" if role == 'kitchen_manager' else "Annapurna Food Rescue Foundation",
            contact_phone="+91 98765 43210",
            address="Campus Block 4, North Wing" if role == 'kitchen_manager' else "Sector 14 Community Hub"
        )
        user.set_password("demo1234")
        db.session.add(user)
        db.session.commit()

    login_user(user)
    role_label = "Kitchen Manager / Food Processor" if role == 'kitchen_manager' else "NGO / Relief Partner"
    flash(f"Switched persona to: {role_label} ({user.organization_name})", "success")
    return redirect(url_for('dashboard.index'))
