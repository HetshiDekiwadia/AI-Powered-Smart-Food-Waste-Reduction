"""
Institutional Cafeteria Data Generator for AI Training
Generates realistic 365-day historical logs of institutional kitchen attendance,
preparation batch volumes, plate waste, and spoilage.
"""

import csv
import random
from datetime import datetime, timedelta

def generate_cafeteria_dataset(filename="sample_cafeteria_data.csv", days=180):
    start_date = datetime.now().date() - timedelta(days=days)
    sessions = ['Breakfast', 'Lunch', 'Snacks', 'Dinner']
    
    headers = [
        'date', 'day_of_week', 'meal_session', 'registered_strength',
        'event_type', 'actual_attendance', 'food_prepared_kg',
        'food_consumed_kg', 'plate_waste_kg', 'surplus_leftover_kg',
        'economic_loss_inr'
    ]

    events_pool = ['None'] * 85 + ['Exam Period'] * 8 + ['Holiday/Long Weekend'] * 5 + ['College Festival / Celebration'] * 2

    session_turnout = {
        'Breakfast': (0.55, 0.70, 0.35), # (min_turnout, max_turnout, kg_per_head)
        'Lunch': (0.80, 0.95, 0.50),
        'Snacks': (0.35, 0.55, 0.25),
        'Dinner': (0.75, 0.92, 0.45)
    }

    base_capacity = 800

    rows = []
    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)
        dow = current_date.weekday()
        event = random.choice(events_pool)

        # Weekend dampener
        weekend_factor = 0.75 if dow in [5, 6] else (0.88 if dow == 4 else 1.0)
        event_factor = 0.6 if event == 'Holiday/Long Weekend' else (1.15 if event == 'College Festival / Celebration' else 1.0)

        for session in sessions:
            min_t, max_t, kg_per_head = session_turnout[session]
            raw_rate = random.uniform(min_t, max_t) * weekend_factor * event_factor
            rate = max(0.25, min(0.98, raw_rate))

            actual_attendance = int(round(base_capacity * rate))
            
            # Traditional uncalibrated kitchen prepares for ~92-98% capacity
            traditional_portions = int(round(base_capacity * random.uniform(0.90, 0.96)))
            food_prepared_kg = round(traditional_portions * kg_per_head, 1)
            
            food_consumed_kg = round(actual_attendance * kg_per_head * random.uniform(0.92, 0.96), 1)
            
            # Plate waste is ~4-8% of consumed food
            plate_waste_kg = round(food_consumed_kg * random.uniform(0.04, 0.08), 1)
            
            # Surplus leftover is prepared minus consumed
            surplus_leftover_kg = max(0.0, round(food_prepared_kg - food_consumed_kg - plate_waste_kg, 1))
            
            economic_loss_inr = round((plate_waste_kg + surplus_leftover_kg) * 55.0, 2)

            rows.append([
                current_date.strftime('%Y-%m-%d'),
                dow,
                session,
                base_capacity,
                event,
                actual_attendance,
                food_prepared_kg,
                food_consumed_kg,
                plate_waste_kg,
                surplus_leftover_kg,
                economic_loss_inr
            ])

    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

    print(f"Generated {len(rows)} historical records in {filename}")

if __name__ == '__main__':
    generate_cafeteria_dataset("ml_models/sample_cafeteria_data.csv", days=120)
