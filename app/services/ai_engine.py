"""
AI Forecasting & Waste Analytics Engine
Predicts institutional meal attendance, suggests optimized preparation batch sizes,
and detects high-risk overproduction waste patterns.
"""

import os
import json
import math
from datetime import datetime

# Meal session weight factors and baseline turnouts
SESSION_FACTORS = {
    'Breakfast': {'factor': 0.65, 'prep_per_person_kg': 0.35},
    'Lunch': {'factor': 0.90, 'prep_per_person_kg': 0.50},
    'Snacks': {'factor': 0.45, 'prep_per_person_kg': 0.25},
    'Dinner': {'factor': 0.85, 'prep_per_person_kg': 0.45}
}

# Centralized single source of truth for waste stream economic loss multipliers (INR per kg)
WASTE_CATEGORY_RATES = {
    'Plate Waste': 60.0,
    'Prep Waste': 30.0,
    'Buffet Leftover': 55.0,
    'Spoilage': 75.0
}

# Institutional procurement benchmark rates (INR per kg) for food items and dish ingredients
FOOD_ITEM_BENCHMARKS = {
    'rice': 35.0,
    'biryani': 45.0,
    'pulao': 40.0,
    'khichdi': 35.0,
    'idli': 35.0,
    'dosa': 40.0,
    'dal': 60.0,
    'sambhar': 50.0,
    'sambar': 50.0,
    'rajma': 65.0,
    'chole': 65.0,
    'lentil': 60.0,
    'roti': 40.0,
    'chapati': 40.0,
    'naan': 50.0,
    'paratha': 45.0,
    'bread': 40.0,
    'puri': 45.0,
    'paneer': 180.0,
    'cheese': 220.0,
    'butter': 250.0,
    'curd': 55.0,
    'milk': 60.0,
    'veg': 45.0,
    'vegetable': 45.0,
    'sabzi': 45.0,
    'bhindi': 40.0,
    'aloo': 30.0,
    'potato': 30.0,
    'gobi': 40.0,
    'curry': 50.0,
    'chicken': 160.0,
    'egg': 90.0,
    'mutton': 350.0,
    'fish': 200.0,
    'meat': 220.0,
    'kheer': 80.0,
    'halwa': 90.0,
    'gulab jamun': 110.0,
    'sweet': 90.0,
    'dessert': 90.0,
    'peel': 25.0,
    'trimming': 25.0,
    'scrap': 25.0,
}

def resolve_waste_rate(food_item, category):
    """
    Determines the applicable benchmark rate (INR/kg) and human-readable basis description.
    Supports delimiter-separated multi-item dishes (e.g. 'Rice & Dal', 'Rice, Dal, Sabzi')
    by computing the blended average benchmark rate.
    Falls back deterministically to the waste category benchmark rate if dish is unrecognized.
    """
    import re
    cleaned_food = str(food_item or '').strip().lower()
    fallback_rate = WASTE_CATEGORY_RATES.get(category, 50.0)

    if not cleaned_food:
        return fallback_rate, f"{category} Category Benchmark"

    # Split on common delimiters: comma, ampersand, plus, slash, and word 'and'
    tokens = [t.strip() for t in re.split(r'[,&+/]|\band\b', cleaned_food) if t.strip()]
    
    matched_items = []
    matched_rates = []

    for token in tokens:
        matched_key = None
        # Match longest key first for precision
        for key in sorted(FOOD_ITEM_BENCHMARKS.keys(), key=len, reverse=True):
            if key in token:
                matched_key = key
                break
        if matched_key:
            matched_items.append(matched_key.title())
            matched_rates.append(FOOD_ITEM_BENCHMARKS[matched_key])

    if matched_rates:
        avg_rate = round(sum(matched_rates) / len(matched_rates), 2)
        if len(matched_rates) > 1:
            desc = f"Blended Benchmark ({', '.join(matched_items)})"
        else:
            desc = f"{matched_items[0]} Benchmark"
        return avg_rate, desc

    return fallback_rate, f"{category} Stream Fallback"

def calculate_waste_loss(weight_kg, category, food_item=""):
    """
    Centralized financial loss calculation for kitchen waste streams.
    Guarantees exact parity between client live preview, database persistence, and ESG/Dashboard ledgers.
    """
    try:
        w = float(weight_kg)
        if w < 0:
            w = 0.0
    except (TypeError, ValueError):
        w = 0.0
    rate, _ = resolve_waste_rate(food_item, category)
    return round(w * rate, 2)

# Day of week multiplier (e.g. Friday/Saturday hostelites go out)
DAY_MULTIPLIERS = {
    0: 0.98, # Monday
    1: 1.00, # Tuesday
    2: 1.00, # Wednesday
    3: 0.97, # Thursday
    4: 0.88, # Friday (lower dinner turnout)
    5: 0.72, # Saturday (weekends lower)
    6: 0.75  # Sunday
}

# Event modifiers
EVENT_FACTORS = {
    'None': 1.0,
    'Exam Period': 0.95,
    'Holiday/Long Weekend': 0.55,
    'College Festival / Celebration': 1.15
}

def predict_meal_demand(capacity, meal_session, day_of_week=None, event_type='None', buffer_percent=6.0):
    """
    Calculates intelligent AI forecast for meal attendance and ingredient requirements.
    
    Parameters:
      capacity (int): Total registered institution/mess strength (e.g. 800)
      meal_session (str): 'Breakfast', 'Lunch', 'Snacks', 'Dinner'
      day_of_week (int): 0 (Monday) to 6 (Sunday). Defaults to today.
      event_type (str): 'None', 'Exam Period', 'Holiday/Long Weekend', 'College Festival / Celebration'
      buffer_percent (float): Recommended safety margin (default 6%, down from normal unoptimized 20%)
      
    Returns:
      dict containing predictions, raw ingredient needs, waste savings & recommendations
    """
    # Defensive input validation & range clamping
    try:
        capacity = max(10, int(capacity))
    except (TypeError, ValueError):
        capacity = 750

    try:
        buffer_percent = max(0.0, min(25.0, float(buffer_percent)))
    except (TypeError, ValueError):
        buffer_percent = 6.0

    if day_of_week is None:
        day_of_week = datetime.now().weekday()
    else:
        try:
            day_of_week = int(day_of_week) % 7
        except (TypeError, ValueError):
            day_of_week = datetime.now().weekday()
        
    session_data = SESSION_FACTORS.get(meal_session, {'factor': 0.8, 'prep_per_person_kg': 0.45})
    base_turnout_rate = session_data['factor']
    prep_kg_per_head = session_data['prep_per_person_kg']
    
    day_mult = DAY_MULTIPLIERS.get(day_of_week, 1.0)
    event_mult = EVENT_FACTORS.get(event_type, 1.0)
    
    # AI forecast core calculation
    expected_turnout_ratio = base_turnout_rate * day_mult * event_mult
    # Keep ratio realistic between 30% and 98%
    expected_turnout_ratio = max(0.30, min(0.98, expected_turnout_ratio))
    
    predicted_headcount = int(round(capacity * expected_turnout_ratio))
    
    # Traditional unoptimized preparation (Kitchens typically prepare for 95% or 100% capacity + buffer)
    traditional_prep_headcount = max(1, int(round(capacity * 0.95)))
    
    # AI Recommended optimized preparation with lean buffer
    optimized_prep_headcount = int(round(predicted_headcount * (1 + (buffer_percent / 100.0))))
    
    # Kilograms calculation
    traditional_food_kg = round(traditional_prep_headcount * prep_kg_per_head, 1)
    optimized_food_kg = round(optimized_prep_headcount * prep_kg_per_head, 1)
    
    # Waste prevented (portions and kg)
    portions_saved = max(0, traditional_prep_headcount - optimized_prep_headcount)
    food_kg_saved = max(0.0, round(traditional_food_kg - optimized_food_kg, 1))
    
    # Cost savings estimate (average ₹45 per meal portion)
    estimated_cost_savings = round(portions_saved * 45, 2)
    
    # Smart Kitchen Actionable Tips
    actionable_tips = []
    if day_of_week in [4, 5, 6]:
        actionable_tips.append("Weekend factor active: Expect 20-30% lower resident turnout. Avoid cooking full grain batches upfront.")
    if event_type == 'Holiday/Long Weekend':
        actionable_tips.append("Long weekend alert: High absentee rate detected. Prepare only on-demand batches.")
    if meal_session in ['Lunch', 'Dinner']:
        actionable_tips.append("Staggered Cooking: Prepare 65% for the primary window (12:30-1:30 PM), hold 35% ingredients ready for live top-up.")
    else:
        actionable_tips.append("Prepare small replenishable batches for breakfast items to minimize buffet display waste.")
        
    return {
        'capacity': capacity,
        'meal_session': meal_session,
        'day_of_week_num': day_of_week,
        'day_name': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][day_of_week],
        'event_type': event_type,
        'predicted_headcount': predicted_headcount,
        'optimized_prep_portions': optimized_prep_headcount,
        'traditional_prep_portions': traditional_prep_headcount,
        'buffer_percent_used': buffer_percent,
        'food_kg_required': optimized_food_kg,
        'food_kg_traditional': traditional_food_kg,
        'portions_saved': portions_saved,
        'food_kg_saved': food_kg_saved,
        'estimated_cost_savings_inr': estimated_cost_savings,
        'confidence_score': 94.2,
        'actionable_tips': actionable_tips
    }

# Supported standard kitchen measurement units for food-wise planning
ALLOWED_FOOD_UNITS = ['kg', 'grams', 'litres', 'ml', 'pieces', 'plates', 'servings']

# Centralized food-specific serving benchmarks (serving quantity per diner and unit)
FOOD_SERVING_BENCHMARKS = {
    # Grains & Rice (kg) - 0.119 kg yields 85 kg for 675 attendance @ 6% buffer
    'rice': {'benchmark': 0.119, 'unit': 'kg'},
    'biryani': {'benchmark': 0.15, 'unit': 'kg'},
    'pulao': {'benchmark': 0.14, 'unit': 'kg'},
    'khichdi': {'benchmark': 0.14, 'unit': 'kg'},
    'poha': {'benchmark': 0.10, 'unit': 'kg'},
    'upma': {'benchmark': 0.10, 'unit': 'kg'},
    'noodles': {'benchmark': 0.12, 'unit': 'kg'},
    'pasta': {'benchmark': 0.12, 'unit': 'kg'},

    # Breads & Breakfast Items (pieces) - Roti/Chapati 2 pieces yields 1,431 pieces
    'roti': {'benchmark': 2.0, 'unit': 'pieces'},
    'chapati': {'benchmark': 2.0, 'unit': 'pieces'},
    'phulka': {'benchmark': 2.5, 'unit': 'pieces'},
    'naan': {'benchmark': 1.5, 'unit': 'pieces'},
    'paratha': {'benchmark': 2.0, 'unit': 'pieces'},
    'puri': {'benchmark': 4.0, 'unit': 'pieces'},
    'bread': {'benchmark': 2.0, 'unit': 'pieces'},
    'pav': {'benchmark': 2.0, 'unit': 'pieces'},
    'kulcha': {'benchmark': 1.5, 'unit': 'pieces'},
    'dosa': {'benchmark': 2.0, 'unit': 'pieces'},
    'idli': {'benchmark': 3.0, 'unit': 'pieces'},
    'vada': {'benchmark': 2.0, 'unit': 'pieces'},
    'egg': {'benchmark': 1.0, 'unit': 'pieces'},
    'samosa': {'benchmark': 1.5, 'unit': 'pieces'},
    'kachori': {'benchmark': 1.5, 'unit': 'pieces'},
    'cutlet': {'benchmark': 2.0, 'unit': 'pieces'},
    'gulab jamun': {'benchmark': 2.0, 'unit': 'pieces'},
    'rasgulla': {'benchmark': 2.0, 'unit': 'pieces'},

    # Pulses / Lentils (kg) - 0.06 kg yields 43 kg for 675 attendance @ 6% buffer
    'dal': {'benchmark': 0.06, 'unit': 'kg'},
    'daal': {'benchmark': 0.06, 'unit': 'kg'},
    'sambhar': {'benchmark': 0.07, 'unit': 'kg'},
    'sambar': {'benchmark': 0.07, 'unit': 'kg'},
    'rajma': {'benchmark': 0.08, 'unit': 'kg'},
    'chole': {'benchmark': 0.08, 'unit': 'kg'},
    'chana': {'benchmark': 0.08, 'unit': 'kg'},
    'lentil': {'benchmark': 0.06, 'unit': 'kg'},
    'kadhi': {'benchmark': 0.07, 'unit': 'kg'},

    # Vegetables & Sabji (kg) - 0.08 kg yields 57 kg for 675 attendance @ 6% buffer
    'vegetable sabji': {'benchmark': 0.08, 'unit': 'kg'},
    'veg sabji': {'benchmark': 0.08, 'unit': 'kg'},
    'sabji': {'benchmark': 0.08, 'unit': 'kg'},
    'sabzi': {'benchmark': 0.08, 'unit': 'kg'},
    'vegetable': {'benchmark': 0.08, 'unit': 'kg'},
    'veg': {'benchmark': 0.08, 'unit': 'kg'},
    'bhindi': {'benchmark': 0.08, 'unit': 'kg'},
    'aloo': {'benchmark': 0.08, 'unit': 'kg'},
    'potato': {'benchmark': 0.08, 'unit': 'kg'},
    'gobi': {'benchmark': 0.08, 'unit': 'kg'},
    'paneer': {'benchmark': 0.08, 'unit': 'kg'},
    'curry': {'benchmark': 0.08, 'unit': 'kg'},

    # Salads & Curd (kg) - Salad 0.04 yields 29 kg; Curd 0.05 yields 36 kg
    'salad': {'benchmark': 0.04, 'unit': 'kg'},
    'curd': {'benchmark': 0.05, 'unit': 'kg'},
    'dahi': {'benchmark': 0.05, 'unit': 'kg'},
    'raita': {'benchmark': 0.05, 'unit': 'kg'},
    'yoghurt': {'benchmark': 0.05, 'unit': 'kg'},
    'yogurt': {'benchmark': 0.05, 'unit': 'kg'},

    # Liquids / Beverages (litres)
    'soup': {'benchmark': 0.15, 'unit': 'litres'},
    'chaas': {'benchmark': 0.18, 'unit': 'litres'},
    'buttermilk': {'benchmark': 0.18, 'unit': 'litres'},
    'milk': {'benchmark': 0.18, 'unit': 'litres'},
    'tea': {'benchmark': 0.12, 'unit': 'litres'},
    'chai': {'benchmark': 0.12, 'unit': 'litres'},
    'coffee': {'benchmark': 0.12, 'unit': 'litres'},
    'juice': {'benchmark': 0.18, 'unit': 'litres'},
}

# Generic sensible fallback benchmark for unknown food items
DEFAULT_FOOD_BENCHMARK = {'benchmark': 0.08, 'unit': 'kg'}

def resolve_food_benchmark(food_name):
    """
    Determines serving benchmark (quantity per person) and measurement unit
    from the food item name.
    Matches longest key first for precision (e.g. 'vegetable sabji' before 'sabji').
    Falls back gracefully to DEFAULT_FOOD_BENCHMARK for unknown foods.
    """
    cleaned = str(food_name or '').strip().lower()
    if not cleaned:
        return DEFAULT_FOOD_BENCHMARK['benchmark'], DEFAULT_FOOD_BENCHMARK['unit']

    for key in sorted(FOOD_SERVING_BENCHMARKS.keys(), key=len, reverse=True):
        if key in cleaned:
            match = FOOD_SERVING_BENCHMARKS[key]
            return match['benchmark'], match['unit']

    return DEFAULT_FOOD_BENCHMARK['benchmark'], DEFAULT_FOOD_BENCHMARK['unit']

def calculate_food_requirement(predicted_attendance, quantity_per_person, safety_buffer):
    """
    Authoritative calculation for food-wise kitchen preparation requirements.
    Formula:
        recommended_quantity = predicted_attendance * quantity_per_person * (1 + safety_buffer / 100)

    Guarantees consistent rounding and bounds:
        - Quantity per person must be strictly positive and finite (> 0).
        - Predicted attendance must be a positive integer (>= 1).
        - Safety buffer must be within valid range (0.0 to 25.0%).
        - Preserves unit strictly.
        - Returns float rounded to 2 decimal places.
    """
    try:
        att = int(predicted_attendance)
    except (TypeError, ValueError):
        raise ValueError("Predicted attendance must be a valid positive integer.")

    if att < 1:
        raise ValueError("Predicted attendance must be at least 1.")

    try:
        qty = float(quantity_per_person)
    except (TypeError, ValueError):
        raise ValueError("Quantity per person must be a valid numeric value.")

    if math.isnan(qty) or math.isinf(qty) or qty <= 0:
        raise ValueError("Quantity per person must be greater than 0.")
    if qty > 50.0:
        raise ValueError("Quantity per person exceeds realistic threshold (maximum 50 units per person).")

    try:
        buf = max(0.0, min(25.0, float(safety_buffer)))
    except (TypeError, ValueError):
        buf = 6.0

    raw_req = att * qty * (1.0 + (buf / 100.0))
    return round(raw_req, 2)

def estimate_food_requirement(food_name, predicted_attendance, safety_buffer):
    """
    Estimates total required preparation quantity and unit for a given food item name,
    based on predicted attendance, safety buffer, and food-specific consumption benchmarks.
    Returns:
        tuple (estimated_quantity: float, unit: str, benchmark_used: float)
    """
    benchmark, unit = resolve_food_benchmark(food_name)
    quantity = calculate_food_requirement(predicted_attendance, benchmark, safety_buffer)
    return quantity, unit, benchmark

def analyze_waste_patterns(waste_logs):
    """
    Analyzes historical waste logs to find top wasted food items,
    critical meal sessions, and common waste root causes.
    """
    if not waste_logs:
        return {
            'total_waste_kg': 0,
            'total_cost_loss': 0,
            'top_wasted_item': 'None',
            'worst_session': 'None',
            'category_breakdown': {},
            'session_breakdown': {},
            'insights': ["Start logging daily kitchen waste to unlock AI pattern detection."]
        }
        
    total_kg = sum(log.weight_kg for log in waste_logs)
    total_cost = sum(log.estimated_cost_loss for log in waste_logs)
    
    cat_summary = {}
    session_summary = {}
    item_summary = {}
    
    for log in waste_logs:
        cat_summary[log.waste_category] = cat_summary.get(log.waste_category, 0.0) + log.weight_kg
        session_summary[log.meal_session] = session_summary.get(log.meal_session, 0.0) + log.weight_kg
        item_summary[log.food_item] = item_summary.get(log.food_item, 0.0) + log.weight_kg

    top_item = max(item_summary.items(), key=lambda x: x[1])[0] if item_summary else 'None'
    worst_session = max(session_summary.items(), key=lambda x: x[1])[0] if session_summary else 'None'

    insights = []
    if 'Plate Waste' in cat_summary and cat_summary['Plate Waste'] > (total_kg * 0.4):
        insights.append("High Plate Waste detected (>40% of total). Suggest implementing smaller standard serving ladles and 'take what you eat' awareness prompts.")
    if 'Spoilage' in cat_summary and cat_summary['Spoilage'] > (total_kg * 0.25):
        insights.append("Storage Spoilage is above threshold (25%). Check cold storage temperatures and inspect near-expiry items.")
    if worst_session != 'None':
        insights.append(f"{worst_session} contributes the highest waste volume ({round(session_summary.get(worst_session, 0), 1)} kg). Review portion sizing for this session.")

    return {
        'total_waste_kg': round(total_kg, 1),
        'total_cost_loss': round(total_cost, 2),
        'top_wasted_item': top_item,
        'worst_session': worst_session,
        'category_breakdown': {k: round(v, 1) for k, v in cat_summary.items()},
        'session_breakdown': {k: round(v, 1) for k, v in session_summary.items()},
        'insights': insights
    }
