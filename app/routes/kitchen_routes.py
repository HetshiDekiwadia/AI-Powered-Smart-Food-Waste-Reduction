from datetime import datetime, timezone, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import WasteLog, InventoryItem
from app.services.ai_engine import calculate_waste_loss, WASTE_CATEGORY_RATES
from app.decorators import kitchen_manager_required

kitchen_bp = Blueprint('kitchen', __name__)

ALLOWED_MEAL_SESSIONS = ['Breakfast', 'Lunch', 'Snacks', 'Dinner']
ALLOWED_WASTE_CATEGORIES = ['Plate Waste', 'Prep Waste', 'Buffet Leftover', 'Spoilage']

@kitchen_bp.route('/waste/log', methods=['GET', 'POST'])
@login_required
@kitchen_manager_required
def log_waste():
    today_str = datetime.now(timezone.utc).date().strftime('%Y-%m-%d')
    form_data = {
        'date': today_str,
        'meal_session': 'Lunch',
        'waste_category': 'Plate Waste',
        'food_item': '',
        'weight_kg': ''
    }

    if request.method == 'POST':
        date_str = request.form.get('date', '').strip()
        meal_session = request.form.get('meal_session', '').strip()
        waste_category = request.form.get('waste_category', '').strip()
        food_item = request.form.get('food_item', '').strip()
        weight_raw = request.form.get('weight_kg', '').strip()

        form_data.update({
            'date': date_str or today_str,
            'meal_session': meal_session or 'Lunch',
            'waste_category': waste_category or 'Plate Waste',
            'food_item': food_item,
            'weight_kg': weight_raw
        })

        # Server-side validation: Date
        if not date_str:
            flash("Please enter a valid entry date.", "warning")
            return render_template('kitchen/log_waste.html', today_str=today_str, form_data=form_data)

        try:
            log_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid date format provided. Please use YYYY-MM-DD.", "warning")
            return render_template('kitchen/log_waste.html', today_str=today_str, form_data=form_data)

        # Server-side validation: Meal Session
        if meal_session not in ALLOWED_MEAL_SESSIONS:
            flash("Please select a valid meal session (Breakfast, Lunch, Snacks, Dinner).", "warning")
            return render_template('kitchen/log_waste.html', today_str=today_str, form_data=form_data)

        # Server-side validation: Waste Category
        if waste_category not in ALLOWED_WASTE_CATEGORIES:
            flash("Please select a valid waste category.", "warning")
            return render_template('kitchen/log_waste.html', today_str=today_str, form_data=form_data)

        # Server-side validation: Food Item
        if not food_item or len(food_item) < 2:
            flash("Please enter the specific food item or dish name (at least 2 characters).", "warning")
            return render_template('kitchen/log_waste.html', today_str=today_str, form_data=form_data)

        # Server-side validation: Waste Weight
        if not weight_raw:
            flash("Please enter the measured waste weight in kilograms.", "warning")
            return render_template('kitchen/log_waste.html', today_str=today_str, form_data=form_data)

        try:
            weight_kg = round(float(weight_raw), 2)
            if weight_kg <= 0:
                flash("Waste weight must be greater than 0 kg.", "warning")
                return render_template('kitchen/log_waste.html', today_str=today_str, form_data=form_data)
            if weight_kg > 2000.0:
                flash("Measured waste weight exceeds maximum realistic single batch threshold (2,000 kg).", "warning")
                return render_template('kitchen/log_waste.html', today_str=today_str, form_data=form_data)
        except (ValueError, TypeError):
            flash("Please enter a valid numeric value for waste weight.", "warning")
            return render_template('kitchen/log_waste.html', today_str=today_str, form_data=form_data)

        # Authoritative single source of truth for economic loss (food benchmark or category fallback)
        estimated_cost_loss = calculate_waste_loss(weight_kg, waste_category, food_item)

        new_log = WasteLog(
            date=log_date,
            meal_session=meal_session,
            waste_category=waste_category,
            food_item=food_item,
            weight_kg=weight_kg,
            reason=None,
            estimated_cost_loss=estimated_cost_loss,
            logged_by_id=current_user.id
        )

        try:
            db.session.add(new_log)
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("A database error occurred while saving the waste log entry. Please try again.", "danger")
            return render_template('kitchen/log_waste.html', today_str=today_str, form_data=form_data)

        flash(f"Successfully recorded {weight_kg} kg of {food_item} ({waste_category}). Estimated economic loss: ₹{estimated_cost_loss:,.2f}.", "success")
        return redirect(url_for('kitchen.waste_history'))

    return render_template('kitchen/log_waste.html', today_str=today_str, form_data=form_data)

@kitchen_bp.route('/waste/history')
@login_required
@kitchen_manager_required
def waste_history():
    logs = WasteLog.query.filter_by(logged_by_id=current_user.id).order_by(WasteLog.date.desc(), WasteLog.created_at.desc()).all()
    total_kg = sum(log.weight_kg for log in logs)
    total_cost = sum(log.estimated_cost_loss for log in logs)

    return render_template('kitchen/waste_history.html', 
                           logs=logs, 
                           total_kg=round(total_kg, 1), 
                           total_cost=round(total_cost, 2))

@kitchen_bp.route('/inventory', methods=['GET', 'POST'])
@login_required
@kitchen_manager_required
def inventory():
    if request.method == 'POST':
        item_name = request.form.get('item_name', '').strip()
        category = request.form.get('category', 'Grains').strip()
        quantity_raw = request.form.get('quantity', '').strip()
        unit = request.form.get('unit', 'kg').strip()
        expiry_str = request.form.get('expiry_date', '').strip()
        min_threshold_raw = request.form.get('min_threshold', '5.0').strip()
        cost_per_unit_raw = request.form.get('cost_per_unit', '50.0').strip()

        # Server-side validation
        if not item_name:
            flash("Item name is required.", "warning")
            return redirect(url_for('kitchen.inventory'))

        try:
            quantity = float(quantity_raw)
            if quantity <= 0:
                flash("Stock quantity must be greater than 0.", "warning")
                return redirect(url_for('kitchen.inventory'))
        except (ValueError, TypeError):
            flash("Please enter a valid numeric stock quantity.", "warning")
            return redirect(url_for('kitchen.inventory'))

        try:
            min_threshold = max(0.0, float(min_threshold_raw)) if min_threshold_raw else 5.0
            cost_per_unit = max(0.0, float(cost_per_unit_raw)) if cost_per_unit_raw else 50.0
        except (ValueError, TypeError):
            min_threshold = 5.0
            cost_per_unit = 50.0

        if not expiry_str:
            flash("Expiry date is required for shelf-life tracking.", "warning")
            return redirect(url_for('kitchen.inventory'))

        try:
            expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            flash("Invalid expiry date format. Please use YYYY-MM-DD.", "warning")
            return redirect(url_for('kitchen.inventory'))

        item = InventoryItem(
            item_name=item_name,
            category=category,
            quantity=round(quantity, 2),
            unit=unit,
            expiry_date=expiry_date,
            min_threshold=round(min_threshold, 2),
            cost_per_unit=round(cost_per_unit, 2)
        )
        db.session.add(item)
        db.session.commit()

        flash(f"Item '{item_name}' ({quantity} {unit}) successfully added to inventory radar.", "success")
        return redirect(url_for('kitchen.inventory'))

    items = InventoryItem.query.order_by(InventoryItem.expiry_date.asc()).all()
    critical_count = sum(1 for item in items if item.status_alert in ['Critical', 'Expired'])
    near_expiry_count = sum(1 for item in items if item.status_alert == 'Near Expiry')

    return render_template('kitchen/inventory.html', 
                           items=items,
                           critical_count=critical_count,
                           near_expiry_count=near_expiry_count)

@kitchen_bp.route('/inventory/delete/<int:item_id>', methods=['POST'])
@login_required
@kitchen_manager_required
def delete_inventory_item(item_id):
    item = InventoryItem.query.get_or_404(item_id)
    item_name = item.item_name
    db.session.delete(item)
    db.session.commit()
    flash(f"Removed '{item_name}' from inventory.", "info")
    return redirect(url_for('kitchen.inventory'))

