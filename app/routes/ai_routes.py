from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from app.models import WasteLog
from app.services.ai_engine import predict_meal_demand, analyze_waste_patterns

ai_bp = Blueprint('ai', __name__)

@ai_bp.route('/forecast', methods=['GET'])
@login_required
def forecast():
    # Default parameters for first render
    capacity = int(request.args.get('capacity', 750))
    meal_session = request.args.get('meal_session', 'Lunch')
    day_of_week = int(request.args.get('day_of_week', 2)) # Default Wednesday
    event_type = request.args.get('event_type', 'None')
    buffer_percent = float(request.args.get('buffer_percent', 6.0))

    prediction = predict_meal_demand(
        capacity=capacity,
        meal_session=meal_session,
        day_of_week=day_of_week,
        event_type=event_type,
        buffer_percent=buffer_percent
    )

    return render_template('kitchen/forecast.html', 
                           pred=prediction,
                           capacity=capacity,
                           meal_session=meal_session,
                           day_of_week=day_of_week,
                           event_type=event_type,
                           buffer_percent=buffer_percent)

@ai_bp.route('/api/predict', methods=['POST'])
@login_required
def api_predict():
    """Real-time JSON endpoint for dynamic UI updates with Chart.js / slider controls."""
    data = request.get_json() or {}
    capacity = int(data.get('capacity', 750))
    meal_session = data.get('meal_session', 'Lunch')
    day_of_week = int(data.get('day_of_week', 2))
    event_type = data.get('event_type', 'None')
    buffer_percent = float(data.get('buffer_percent', 6.0))

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
def analytics():
    logs = WasteLog.query.all()
    analysis = analyze_waste_patterns(logs)
    return render_template('kitchen/waste_analytics.html', analysis=analysis)
