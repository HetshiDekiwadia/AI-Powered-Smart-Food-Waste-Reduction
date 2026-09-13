from flask import Blueprint, render_template, redirect, url_for, flash, request, session, make_response
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from app.models import User
from app.services.redistribution import clean_city_name

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    username = ''
    selected_role = 'kitchen_manager'
    if request.method == 'POST':
        selected_role = request.form.get('role', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        # Server-side validation for selected role
        if not selected_role or selected_role not in ['kitchen_manager', 'ngo']:
            flash("Please select your ecosystem role (Kitchen Manager or NGO Partner).", "warning")
            return render_template('auth/login.html', username=username, selected_role=selected_role)

        # Server-side validation for empty credentials
        if not username and not password:
            flash("Please enter both your username/email and password.", "warning")
            return render_template('auth/login.html', username=username, selected_role=selected_role)
        elif not username:
            flash("Please enter your username or email address.", "warning")
            return render_template('auth/login.html', username=username, selected_role=selected_role)
        elif not password:
            flash("Please enter your password.", "warning")
            return render_template('auth/login.html', username=username, selected_role=selected_role)

        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()

        # Generic authentication check: prevents account enumeration
        if not user or not user.check_password(password):
            flash("Invalid username or password. Please try again.", "danger")
            return render_template('auth/login.html', username=username, selected_role=selected_role)

        # Strict Backend Role Authorization: Validate selected role against actual database role
        if user.role != selected_role:
            if user.role == 'kitchen_manager':
                flash("Role mismatch: This account is registered as a Kitchen Manager, not an NGO Partner. Please select 'Kitchen Manager' to sign in.", "danger")
            else:
                flash("Role mismatch: This account is registered as an NGO Relief Partner, not a Kitchen Manager. Please select 'NGO Partner' to sign in.", "danger")
            return render_template('auth/login.html', username=username, selected_role=selected_role)

        # Credentials and role are strictly verified
        login_user(user, remember=True)
        role_label = "Kitchen Manager" if user.role == 'kitchen_manager' else "NGO Relief Partner"
        flash(f"Welcome back, {user.organization_name}! Signed in as {role_label}.", "success")
        next_page = request.args.get('next')
        # Guard against open redirects or loopbacks to auth endpoints
        if not next_page or not next_page.startswith('/') or next_page.startswith('//') or 'auth/login' in next_page or 'auth/logout' in next_page:
            next_page = url_for('dashboard.index')
        return redirect(next_page)

    return render_template('auth/login.html', username=username, selected_role=selected_role)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        role = request.form.get('role', 'kitchen_manager').strip()
        organization_name = request.form.get('organization_name', '').strip()
        contact_phone = request.form.get('contact_phone', '').strip()
        address = request.form.get('address', '').strip()
        city_raw = request.form.get('city', '')
        city_cleaned = clean_city_name(city_raw)

        form_data = {
            'username': username,
            'email': email,
            'role': role,
            'organization_name': organization_name,
            'contact_phone': contact_phone,
            'address': address,
            'city': city_raw
        }

        # Server-side validation for all required fields
        if not username or not email or not password or not organization_name or not contact_phone or not address:
            flash("All required fields must be completed.", "warning")
            return render_template('auth/register.html', form_data=form_data)

        if len(username) < 3:
            flash("Username must be at least 3 characters long.", "warning")
            return render_template('auth/register.html', form_data=form_data)

        if '@' not in email or '.' not in email.split('@')[-1]:
            flash("Please enter a valid email address.", "warning")
            return render_template('auth/register.html', form_data=form_data)

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "warning")
            return render_template('auth/register.html', form_data=form_data)

        if role not in ['kitchen_manager', 'ngo']:
            flash("Please select a valid institutional ecosystem role.", "warning")
            return render_template('auth/register.html', form_data=form_data)

        # Operating City validation (Required, trimmed, min 2 chars, max 64 chars, reject blank)
        if not city_cleaned:
            flash("Operating City is required. Please specify your operating city.", "warning")
            return render_template('auth/register.html', form_data=form_data)

        if len(city_cleaned) < 2:
            flash("Operating City must be at least 2 characters long.", "warning")
            return render_template('auth/register.html', form_data=form_data)

        if len(city_cleaned) > 64:
            flash("Operating City must not exceed 64 characters.", "warning")
            return render_template('auth/register.html', form_data=form_data)

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or Email is already registered. Please login or use a different credential.", "warning")
            return render_template('auth/register.html', form_data=form_data)

        new_user = User(
            username=username,
            email=email,
            role=role,
            organization_name=organization_name or username,
            contact_phone=contact_phone,
            address=address,
            city=city_cleaned
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        flash("Registration successful! Welcome to the EcoPlate AI ecosystem.", "success")
        return redirect(url_for('dashboard.index'))

    return render_template('auth/register.html', form_data={})

@auth_bp.route('/logout')
def logout():
    logout_user()
    session.clear()
    flash("You have been signed out successfully.", "info")
    response = make_response(redirect(url_for('auth.login')))
    response.delete_cookie('remember_token')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

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
            organization_name="Apex University Central Mega-Mess" if role == 'kitchen_manager' else "Annapurna Food Rescue Foundation",
            contact_phone="+91 98765 43210" if role == 'kitchen_manager' else "+91 98111 22334",
            address="Campus Block B, Dining Complex, North Campus" if role == 'kitchen_manager' else "Unit 12, Community Relief Center, Civil Lines",
            city="Delhi"
        )
        user.set_password("demo1234")
        db.session.add(user)
        db.session.commit()

    login_user(user)
    role_label = "Kitchen Manager / Food Processor" if role == 'kitchen_manager' else "NGO / Relief Partner"
    flash(f"Switched persona to: {role_label} ({user.organization_name})", "success")
    return redirect(url_for('dashboard.index'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        organization_name = request.form.get('organization_name', '').strip()
        contact_phone = request.form.get('contact_phone', '').strip()
        address = request.form.get('address', '').strip()
        city_raw = request.form.get('city', '')
        city_cleaned = clean_city_name(city_raw)

        if not organization_name:
            flash("Organization name is required.", "warning")
            return render_template('auth/profile.html', user=current_user)

        if not address:
            flash("Operating address is required.", "warning")
            return render_template('auth/profile.html', user=current_user)

        if not city_cleaned:
            flash("Operating City is required. Please specify your operating city.", "warning")
            return render_template('auth/profile.html', user=current_user)

        if len(city_cleaned) < 2:
            flash("Operating City must be at least 2 characters long.", "warning")
            return render_template('auth/profile.html', user=current_user)

        if len(city_cleaned) > 64:
            flash("Operating City must not exceed 64 characters.", "warning")
            return render_template('auth/profile.html', user=current_user)

        current_user.organization_name = organization_name
        current_user.contact_phone = contact_phone
        current_user.address = address
        current_user.city = city_cleaned
        db.session.commit()

        flash("Profile and Operating City updated successfully! Local surplus visibility has been updated.", "success")
        return redirect(url_for('auth.profile'))

    return render_template('auth/profile.html', user=current_user)

