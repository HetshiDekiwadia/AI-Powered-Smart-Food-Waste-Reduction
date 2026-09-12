from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from app.models import WasteLog, SurplusListing, Claim, InventoryItem
from app.services.esg_metrics import calculate_impact_metrics

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def root():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    return redirect(url_for('auth.login'))

@dashboard_bp.route('/dashboard')
@login_required
def index():
    waste_logs = WasteLog.query.order_by(WasteLog.date.desc()).all()
    inventory_items = InventoryItem.query.all()
    surplus_listings = SurplusListing.query.order_by(SurplusListing.created_at.desc()).all()
    completed_claims = Claim.query.filter_by(status='Delivered').all()

    # Core KPI aggregations
    total_waste_kg = round(sum(log.weight_kg for log in waste_logs), 1)
    total_waste_cost = round(sum(log.estimated_cost_loss for log in waste_logs), 2)
    
    # Meals saved via surplus redistribution
    meals_saved_count = sum(c.beneficiaries_count for c in completed_claims)
    # Approx 0.4 kg per meal portion
    food_kg_saved = round(meals_saved_count * 0.4, 1)

    # ESG impact metrics
    impact = calculate_impact_metrics(meals_saved_count, food_kg_saved)

    # Inventory critical items count
    critical_inventory = [item for item in inventory_items if item.status_alert in ['Critical', 'Near Expiry', 'Expired']]

    # Prepare chart data (Last 7 days or sessions)
    categories = {}
    for log in waste_logs:
        categories[log.waste_category] = categories.get(log.waste_category, 0.0) + log.weight_kg

    category_labels = list(categories.keys()) or ['Plate Waste', 'Prep Waste', 'Spoilage', 'Buffet Leftover']
    category_values = [round(categories.get(k, 0.0), 1) for k in category_labels]

    return render_template('dashboard/index.html',
                           total_waste_kg=total_waste_kg,
                           total_waste_cost=total_waste_cost,
                           meals_saved_count=meals_saved_count,
                           impact=impact,
                           critical_inventory=critical_inventory[:5],
                           recent_logs=waste_logs[:6],
                           active_listings=[l for l in surplus_listings if l.status == 'Available'][:4],
                           category_labels=category_labels,
                           category_values=category_values)

@dashboard_bp.route('/esg-report')
@login_required
def esg_report():
    completed_claims = Claim.query.filter_by(status='Delivered').all()
    meals_saved_count = sum(c.beneficiaries_count for c in completed_claims)
    food_kg_saved = round(meals_saved_count * 0.4, 1)
    
    impact = calculate_impact_metrics(meals_saved_count, food_kg_saved)
    return render_template('dashboard/esg_report.html', impact=impact, claims=completed_claims)
