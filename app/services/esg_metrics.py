"""
ESG and Environmental Impact Calculation Service
Calculates real-world sustainability benchmarks:
- CO2 Equivalent Reduction (kg)
- Embedded Water Saved (Liters)
- Total Meals Saved
- Total Financial Cost Avoidance (INR)
"""

from config import Config

def calculate_impact_metrics(total_meals_saved, total_food_kg_saved, total_cost_saved=None):
    """
    Given total meals/kg saved, compute standard UNEP/FAO equivalent impact.
    """
    co2_saved = round(total_food_kg_saved * Config.CO2_PER_KG_FOOD, 2)
    water_saved = round(total_food_kg_saved * Config.WATER_PER_KG_FOOD, 1)
    
    if total_cost_saved is None:
        cost_saved = round(total_meals_saved * Config.AVG_COST_PER_MEAL, 2)
    else:
        cost_saved = round(total_cost_saved, 2)

    # Equivalency metrics for intuitive visualization
    # 1 passenger car emits ~0.19 kg CO2 per km
    car_kms_equivalent = round(co2_saved / 0.19, 1)
    # Average shower uses ~65 liters of water
    showers_equivalent = round(water_saved / 65, 0)
    # Trees planted equivalent (~21 kg CO2 absorbed per tree per year)
    trees_equivalent = round(co2_saved / 21.7, 1)

    return {
        'meals_saved': int(total_meals_saved),
        'food_kg_saved': round(total_food_kg_saved, 1),
        'co2_saved_kg': co2_saved,
        'water_saved_liters': water_saved,
        'cost_saved_inr': cost_saved,
        'car_kms_equivalent': car_kms_equivalent,
        'showers_equivalent': int(showers_equivalent),
        'trees_equivalent': trees_equivalent
    }
