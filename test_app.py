"""
Automated Test Suite for EcoPlate AI Flask Application
Tests route availability, model relationships, and AI forecast calculation.
"""

from app import create_app, db
from app.models import User, WasteLog, InventoryItem, SurplusListing, Claim
from app.services.ai_engine import predict_meal_demand, analyze_waste_patterns
from app.services.esg_metrics import calculate_impact_metrics

def run_tests():
    print("Initializing test suite...")
    app = create_app()
    app.config['TESTING'] = True

    with app.test_client() as client:
        # Test 1: Public login page
        resp = client.get('/auth/login')
        assert resp.status_code == 200, f"Login failed: {resp.status_code}"
        print("[PASS] Route: /auth/login returns 200 OK")

        # Test 2: Public register page
        resp = client.get('/auth/register')
        assert resp.status_code == 200, f"Register failed: {resp.status_code}"
        print("[PASS] Route: /auth/register returns 200 OK")

        # Test 3: Demo login as kitchen manager
        resp = client.get('/auth/demo-login/kitchen_manager', follow_redirects=True)
        assert resp.status_code == 200, f"Demo login failed: {resp.status_code}"
        assert b"Apex University Central Mega-Mess" in resp.data, "Organization name not in dashboard"
        print("[PASS] Demo Login & Dashboard Session: 200 OK (Kitchen Manager)")

        # Test 4: Waste history page
        resp = client.get('/kitchen/waste/history')
        assert resp.status_code == 200, f"Waste history failed: {resp.status_code}"
        assert b"Food Waste Measurement Ledger" in resp.data
        print("[PASS] Route: /kitchen/waste/history returns 200 OK")

        # Test 5: Inventory page
        resp = client.get('/kitchen/inventory')
        assert resp.status_code == 200, f"Inventory failed: {resp.status_code}"
        assert b"Basmati Rice Grade-A" in resp.data
        print("[PASS] Route: /kitchen/inventory returns 200 OK")

        # Test 6: AI Demand Forecast page
        resp = client.get('/ai/forecast?capacity=800&meal_session=Lunch')
        assert resp.status_code == 200, f"AI forecast failed: {resp.status_code}"
        assert b"Target Portions to Cook" in resp.data
        print("[PASS] Route: /ai/forecast returns 200 OK")

        # Test 7: AI JSON API
        resp = client.post('/ai/api/predict', json={
            'capacity': 1000,
            'meal_session': 'Dinner',
            'day_of_week': 4,
            'event_type': 'None',
            'buffer_percent': 5.0
        })
        assert resp.status_code == 200, f"AI API failed: {resp.status_code}"
        json_data = resp.get_json()
        assert 'predicted_headcount' in json_data
        assert 'optimized_prep_portions' in json_data
        print(f"[PASS] Route: /ai/api/predict returns 200 OK (Predicted {json_data['predicted_headcount']} eaters, {json_data['optimized_prep_portions']} portions)")

        # Test 8: Marketplace page
        resp = client.get('/donation/marketplace')
        assert resp.status_code == 200, f"Marketplace failed: {resp.status_code}"
        assert b"Live Surplus Food Redistribution Feed" in resp.data
        print("[PASS] Route: /donation/marketplace returns 200 OK")

        # Test 9: ESG Report page
        resp = client.get('/esg-report')
        assert resp.status_code == 200, f"ESG Report failed: {resp.status_code}"
        assert b"Institutional ESG & Sustainability Audit Report" in resp.data
        print("[PASS] Route: /esg-report returns 200 OK")

        # Test 10: Switch to NGO Persona
        resp = client.get('/auth/demo-login/ngo', follow_redirects=True)
        assert resp.status_code == 200
        assert b"Annapurna Food Rescue Foundation" in resp.data
        print("[PASS] Demo Persona Switch to NGO: 200 OK")

        # Test 11: AI logic unit tests
        pred = predict_meal_demand(capacity=600, meal_session='Lunch')
        assert pred['predicted_headcount'] > 0
        assert pred['portions_saved'] > 0
        print("[PASS] AI Engine Unit Test passed")

        # Test 12: ESG calculation unit test
        impact = calculate_impact_metrics(100, 40.0)
        assert impact['co2_saved_kg'] == 100.0
        assert impact['water_saved_liters'] == 40000.0
        print("[PASS] ESG Metrics Unit Test passed")

    print("\nALL 12 AUTOMATED TESTS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    run_tests()
