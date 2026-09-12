from datetime import datetime, timezone, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import WasteLog, InventoryItem

kitchen_bp = Blueprint('kitchen', __name__)

AVG_COST_PER_KG_WASTE = {
    'Grains & Bread': 40.0,
    'Cooked Meals / Curries': 65.0,
    'Dairy & Desserts': 90.0,
    'Raw Vegetables & Prep Trimmings': 30.0,
    'Buffet Leftovers': 60.0
}

@kitchen_bp.route('/waste/log', methods=['GET', 'POST'])
@login_required
def log_waste():
    if request.method == 'POST':
        date_str = request.form.get('date')
        meal_session = request.form.get('meal_session', 'Lunch')
        waste_category = request.form.get('waste_category', 'Plate Waste')
        food_item = request.form.get('food_item', '').strip()
        weight_kg = float(request.form.get('weight_kg', 0.0))
        reason = request.form.get('reason', '').strip()

        try:
            log_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.now(timezone.utc).date()
        except ValueError:
            log_date = datetime.now(timezone.utc).date()

        # Cost calculation based on item category
        multiplier = 50.0
        for cat, cost in AVG_COST_PER_KG_WASTE.items():
            if cat.lower() in food_item.lower() or cat.lower() in waste_category.lower():
                multiplier = cost
                break
        estimated_cost_loss = round(weight_kg * multiplier, 2)

        new_log = WasteLog(
            date=log_date,
            meal_session=meal_session,
            waste_category=waste_category,
            food_item=food_item or "Assorted Mixed Food",
            weight_kg=weight_kg,
            reason=reason,
            estimated_cost_loss=estimated_cost_loss,
            logged_by_id=current_user.id
        )
        db.session.add(new_log)
        db.session.commit()

        flash(f"Logged {weight_kg} kg waste for {food_item}. Financial loss estimated at ₹{estimated_cost_loss}.", "success")
        return redirect(url_for('kitchen.waste_history'))

    today_str = datetime.now(timezone.utc).date().strftime('%Y-%m-%d')
    return render_template('kitchen/log_waste.html', today_str=today_str)

@kitchen_bp.route('/waste/history')
@login_required
def waste_history():
    logs = WasteLog.query.order_by(WasteLog.created_at.desc()).all()
    total_kg = sum(log.weight_kg for log in logs)
    total_cost = sum(log.estimated_cost_loss for log in logs)

    return render_template('kitchen/waste_history.html', 
                           logs=logs, 
                           total_kg=round(total_kg, 1), 
                           total_cost=round(total_cost, 2))

@kitchen_bp.route('/inventory', methods=['GET', 'POST'])
@login_required
def inventory():
    if request.method == 'POST':
        item_name = request.form.get('item_name', '').strip()
        category = request.form.get('category', 'Grains')
        quantity = float(request.form.get('quantity', 0.0))
        unit = request.form.get('unit', 'kg')
        expiry_str = request.form.get('expiry_date')
        min_threshold = float(request.form.get('min_threshold', 5.0))
        cost_per_unit = float(request.form.get('cost_per_unit', 50.0))

        try:
            expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            expiry_date = (datetime.now(timezone.utc) + timedelta(days=7)).date()

        item = InventoryItem(
            item_name=item_name,
            category=category,
            quantity=quantity,
            unit=unit,
            expiry_date=expiry_date,
            min_threshold=min_threshold,
            cost_per_unit=cost_per_unit
        )
        db.session.add(item)
        db.session.commit()

        flash(f"Item '{item_name}' added to inventory.", "success")
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
def delete_inventory_item(item_id):
    item = InventoryItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash(f"Removed '{item.item_name}' from inventory.", "info")
    return redirect(url_for('kitchen.inventory'))
