from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import func
from app.models import WasteLog, SurplusListing, Claim, InventoryItem
from app.services.esg_metrics import calculate_impact_metrics
from app.services.redistribution import normalize_city, cities_match
from app.decorators import kitchen_manager_required

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def root():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    return redirect(url_for('auth.login'))

@dashboard_bp.route('/dashboard')
@login_required
def index():
    if current_user.role == 'ngo':
        # Dedicated NGO Dashboard data: strictly isolate surplus to the NGO's operating city
        now = datetime.now(timezone.utc)
        if current_user.city and current_user.city.strip():
            norm_city = normalize_city(current_user.city)
            db_candidates = SurplusListing.query.filter(
                SurplusListing.status == 'Available',
                SurplusListing.pickup_city.isnot(None),
                func.lower(func.trim(SurplusListing.pickup_city)) == norm_city
            ).all()
            active_available = [
                l for l in db_candidates
                if cities_match(l.pickup_city, current_user.city) and
                (l.safe_until.replace(tzinfo=timezone.utc) if l.safe_until.tzinfo is None else l.safe_until) > now and
                l.fssai_verified
            ]
        else:
            active_available = []

        available_surplus_count = len(active_available)
        available_surplus_portions = sum(l.quantity_portions for l in active_available)

        # My Active Claims
        my_active_claims = Claim.query.filter_by(ngo_id=current_user.id).filter(
            Claim.status.in_(['Claimed', 'Picked Up'])
        ).order_by(Claim.claimed_at.desc()).all()
        active_claims_count = len(my_active_claims)

        # Meals Received & Completed Deliveries
        my_delivered_claims = Claim.query.filter_by(ngo_id=current_user.id, status='Delivered').all()
        meals_received_count = sum(c.beneficiaries_count for c in my_delivered_claims)
        completed_deliveries_count = len(my_delivered_claims)

        # Recent claims for quick tracking table
        recent_claims = Claim.query.filter_by(ngo_id=current_user.id).order_by(Claim.claimed_at.desc()).limit(6).all()

        return render_template('dashboard/ngo_dashboard.html',
                               available_surplus_count=available_surplus_count,
                               available_surplus_portions=available_surplus_portions,
                               active_claims_count=active_claims_count,
                               meals_received_count=meals_received_count,
                               completed_deliveries_count=completed_deliveries_count,
                               active_claims=my_active_claims,
                               recent_claims=recent_claims,
                               operating_city=current_user.city)

    # Kitchen Manager Dashboard
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
@kitchen_manager_required
def esg_report():
    completed_claims = Claim.query.filter_by(status='Delivered').all()
    meals_saved_count = sum(c.beneficiaries_count for c in completed_claims)
    food_kg_saved = round(meals_saved_count * 0.4, 1)
    
    impact = calculate_impact_metrics(meals_saved_count, food_kg_saved)
    return render_template('dashboard/esg_report.html', impact=impact, claims=completed_claims)

