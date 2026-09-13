from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import WasteLog, FoodPreparationPlan, FoodPreparationItem
from app.services.ai_engine import (
    predict_meal_demand, analyze_waste_patterns, 
    calculate_food_requirement, estimate_food_requirement, resolve_food_benchmark,
    ALLOWED_FOOD_UNITS
)
from app.decorators import kitchen_manager_required

ai_bp = Blueprint('ai', __name__)

@ai_bp.route('/forecast', methods=['GET'])
@login_required
@kitchen_manager_required
def forecast():
    # Defensive parameter parsing and validation
    try:
        capacity = max(10, min(50000, int(request.args.get('capacity', 750))))
    except (TypeError, ValueError):
        capacity = 750

    meal_session = request.args.get('meal_session', 'Lunch').strip()
    if meal_session not in ['Breakfast', 'Lunch', 'Snacks', 'Dinner']:
        meal_session = 'Lunch'

    try:
        day_of_week = int(request.args.get('day_of_week', 2)) % 7
    except (TypeError, ValueError):
        day_of_week = 2

    event_type = request.args.get('event_type', 'None').strip()
    if event_type not in ['None', 'Exam Period', 'Holiday/Long Weekend', 'College Festival / Celebration']:
        event_type = 'None'

    try:
        buffer_percent = max(1.0, min(25.0, float(request.args.get('buffer_percent', 6.0))))
    except (TypeError, ValueError):
        buffer_percent = 6.0

    prediction = predict_meal_demand(
        capacity=capacity,
        meal_session=meal_session,
        day_of_week=day_of_week,
        event_type=event_type,
        buffer_percent=buffer_percent
    )

    # Fetch active plan if specified and owned by current user
    active_plan = None
    active_plan_id = request.args.get('active_plan_id')
    if active_plan_id and current_user.is_authenticated:
        try:
            active_plan = FoodPreparationPlan.query.filter_by(id=int(active_plan_id), user_id=current_user.id).first()
        except (ValueError, TypeError):
            active_plan = None

    # Fetch recent historical plans for the authenticated Kitchen Manager
    saved_plans = []
    if current_user.is_authenticated and current_user.role == 'kitchen_manager':
        saved_plans = FoodPreparationPlan.query.filter_by(user_id=current_user.id).order_by(FoodPreparationPlan.created_at.desc()).limit(10).all()

    return render_template('kitchen/forecast.html', 
                           pred=prediction,
                           capacity=capacity,
                           meal_session=meal_session,
                           day_of_week=day_of_week,
                           event_type=event_type,
                           buffer_percent=buffer_percent,
                           saved_plans=saved_plans,
                           active_plan=active_plan,
                           allowed_units=ALLOWED_FOOD_UNITS)

@ai_bp.route('/food-plan/create', methods=['POST'])
@login_required
@kitchen_manager_required
def create_food_plan():
    # Server-side authorization: Kitchen Managers only
    if current_user.role != 'kitchen_manager':
        flash("Unauthorized: Only Kitchen Managers can create food preparation plans.", "danger")
        return redirect(url_for('ai.forecast'))

    capacity = request.form.get('capacity', '750').strip()
    meal_session = request.form.get('meal_session', 'Lunch').strip()
    day_of_week = request.form.get('day_of_week', '2').strip()
    event_type = request.form.get('event_type', 'None').strip()
    predicted_attendance_raw = request.form.get('predicted_attendance', '').strip()
    safety_buffer_raw = request.form.get('safety_buffer', '6.0').strip()

    # Preserve forecast parameters for seamless redirect
    redirect_kwargs = {
        'capacity': capacity,
        'meal_session': meal_session,
        'day_of_week': day_of_week,
        'event_type': event_type,
        'buffer_percent': safety_buffer_raw or '6.0'
    }

    try:
        predicted_attendance = int(predicted_attendance_raw)
        if predicted_attendance < 1:
            flash("Predicted attendance must be at least 1 person.", "warning")
            return redirect(url_for('ai.forecast', **redirect_kwargs))
    except (TypeError, ValueError):
        flash("Invalid predicted attendance value.", "warning")
        return redirect(url_for('ai.forecast', **redirect_kwargs))

    try:
        safety_buffer = float(safety_buffer_raw)
        if safety_buffer < 0.0 or safety_buffer > 25.0:
            flash("Safety buffer must be between 0% and 25%.", "warning")
            return redirect(url_for('ai.forecast', **redirect_kwargs))
    except (TypeError, ValueError):
        flash("Invalid safety buffer value.", "warning")
        return redirect(url_for('ai.forecast', **redirect_kwargs))

    food_names = request.form.getlist('food_name[]')

    if not food_names or len(food_names) == 0:
        flash("At least one food item is required to generate a preparation plan.", "warning")
        return redirect(url_for('ai.forecast', **redirect_kwargs))

    validated_items = []
    seen_names = set()

    for idx, raw_name in enumerate(food_names):
        name = raw_name.strip()

        # If user left a trailing empty row, skip it if other valid items exist
        if not name:
            if len(food_names) > 1 and len(validated_items) > 0:
                continue
            flash(f"Food item name cannot be blank on row {idx + 1}.", "warning")
            return redirect(url_for('ai.forecast', **redirect_kwargs))

        if len(name) < 2:
            flash(f"Food item name '{name}' must be at least 2 characters long.", "warning")
            return redirect(url_for('ai.forecast', **redirect_kwargs))

        if len(name) > 120:
            flash(f"Food item name '{name}' exceeds maximum length of 120 characters.", "warning")
            return redirect(url_for('ai.forecast', **redirect_kwargs))

        # Case-insensitive duplicate check
        name_lower = name.lower()
        if name_lower in seen_names:
            flash(f"Duplicate food item detected: '{name}'. Please consolidate duplicate entries.", "warning")
            return redirect(url_for('ai.forecast', **redirect_kwargs))
        seen_names.add(name_lower)

        validated_items.append(name)

    if not validated_items:
        flash("Please enter at least one valid food item name.", "warning")
        return redirect(url_for('ai.forecast', **redirect_kwargs))

    if len(validated_items) > 50:
        flash("Maximum limit of 50 menu items exceeded per preparation plan.", "warning")
        return redirect(url_for('ai.forecast', **redirect_kwargs))

    # Atomic transaction execution
    try:
        new_plan = FoodPreparationPlan(
            user_id=current_user.id,
            predicted_attendance=predicted_attendance,
            safety_buffer=safety_buffer,
            meal_session=meal_session
        )
        db.session.add(new_plan)
        db.session.flush() # obtain new_plan.id while keeping transaction open

        for food_name in validated_items:
            est_qty, unit, benchmark = estimate_food_requirement(
                food_name=food_name,
                predicted_attendance=predicted_attendance,
                safety_buffer=safety_buffer
            )
            child_item = FoodPreparationItem(
                plan_id=new_plan.id,
                food_name=food_name,
                unit=unit,
                quantity_per_person=benchmark,
                recommended_quantity=est_qty
            )
            db.session.add(child_item)

        db.session.commit()
        flash(f"AI Food-wise Preparation Plan generated and saved successfully for {len(validated_items)} menu items.", "success")
        redirect_kwargs['active_plan_id'] = new_plan.id
        return redirect(url_for('ai.forecast', **redirect_kwargs))

    except Exception:
        db.session.rollback()
        flash("A database error occurred while saving the food preparation plan. Please try again.", "danger")
        return redirect(url_for('ai.forecast', **redirect_kwargs))

@ai_bp.route('/food-plan/<int:plan_id>', methods=['GET'])
@login_required
@kitchen_manager_required
def view_food_plan(plan_id):
    if current_user.role != 'kitchen_manager':
        flash("Unauthorized: Only Kitchen Managers can view food preparation plans.", "danger")
        return redirect(url_for('ai.forecast'))

    plan = FoodPreparationPlan.query.filter_by(id=plan_id, user_id=current_user.id).first()
    if not plan:
        flash("Food preparation plan not found or access denied.", "warning")
        return redirect(url_for('ai.forecast'))

    return redirect(url_for('ai.forecast',
                            meal_session=plan.meal_session,
                            buffer_percent=plan.safety_buffer,
                            active_plan_id=plan.id))

@ai_bp.route('/api/predict', methods=['POST'])
@login_required
@kitchen_manager_required
def api_predict():
    """Real-time JSON endpoint for dynamic UI updates with Chart.js / slider controls."""
    data = request.get_json() or {}
    try:
        capacity = max(10, min(50000, int(data.get('capacity', 750))))
    except (TypeError, ValueError):
        capacity = 750

    meal_session = str(data.get('meal_session', 'Lunch')).strip()
    if meal_session not in ['Breakfast', 'Lunch', 'Snacks', 'Dinner']:
        meal_session = 'Lunch'

    try:
        day_of_week = int(data.get('day_of_week', 2)) % 7
    except (TypeError, ValueError):
        day_of_week = 2

    event_type = str(data.get('event_type', 'None')).strip()
    if event_type not in ['None', 'Exam Period', 'Holiday/Long Weekend', 'College Festival / Celebration']:
        event_type = 'None'

    try:
        buffer_percent = max(1.0, min(25.0, float(data.get('buffer_percent', 6.0))))
    except (TypeError, ValueError):
        buffer_percent = 6.0

    result = predict_meal_demand(
        capacity=capacity,
        meal_session=meal_session,
        day_of_week=day_of_week,
        event_type=event_type,
        buffer_percent=buffer_percent
    )
    return jsonify(result)

@ai_bp.route('/analytics')
@login_required
@kitchen_manager_required
def analytics():
    logs = WasteLog.query.all()
    analysis = analyze_waste_patterns(logs)
    return render_template('kitchen/waste_analytics.html', analysis=analysis)
