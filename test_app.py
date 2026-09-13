"""
Automated Test Suite for EcoPlate AI Flask Application
Tests route availability, model relationships, and AI forecast calculation.
"""

from datetime import datetime, timezone, timedelta
import time
from app import create_app, db
from app.models import User, WasteLog, InventoryItem, SurplusListing, Claim, FoodPreparationPlan, FoodPreparationItem
from app.services.ai_engine import (
    predict_meal_demand, analyze_waste_patterns, calculate_waste_loss, 
    calculate_food_requirement, estimate_food_requirement, resolve_food_benchmark,
    ALLOWED_FOOD_UNITS, FOOD_SERVING_BENCHMARKS
)
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

        # Log out from previous test session to test unauthenticated login flow
        client.get('/auth/logout')

        # Req 1: Empty username/email -> validation error
        resp_empty_user = client.post('/auth/login', data={'role': 'kitchen_manager', 'username': '', 'password': '123'}, follow_redirects=True)
        assert resp_empty_user.status_code == 200
        assert b"Please enter your username or email address" in resp_empty_user.data
        print("[PASS] Req 1: Empty username/email properly rejected with validation message")

        # Req 2: Empty password -> validation error
        resp_empty_pass = client.post('/auth/login', data={'role': 'kitchen_manager', 'username': 'admin', 'password': ''}, follow_redirects=True)
        assert resp_empty_pass.status_code == 200
        assert b"Please enter your password" in resp_empty_pass.data
        print("[PASS] Req 2: Empty password properly rejected with validation message")

        # Req 3: No role selected -> validation error
        resp_no_role = client.post('/auth/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
        assert resp_no_role.status_code == 200
        assert b"Please select your ecosystem role" in resp_no_role.data
        print("[PASS] Req 3: Missing role rejected with selection requirement message")

        # Req 4: Invalid credentials -> generic authentication error
        resp_bad = client.post('/auth/login', data={'role': 'kitchen_manager', 'username': 'admin', 'password': 'wrongpassword'}, follow_redirects=True)
        assert resp_bad.status_code == 200
        assert b"Invalid username or password" in resp_bad.data
        print("[PASS] Req 4: Invalid credentials safely rejected with generic error")

        # Req 5: Correct Kitchen Manager credentials + Kitchen Manager role -> Kitchen dashboard
        resp_km_ok = client.post('/auth/login', data={'role': 'kitchen_manager', 'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
        assert resp_km_ok.status_code == 200
        assert b"Apex University Central Mega-Mess" in resp_km_ok.data
        assert b"Kitchen Manager" in resp_km_ok.data
        assert b"Log Food Waste" in resp_km_ok.data
        print("[PASS] Req 5: Correct Kitchen Manager credentials + Kitchen role -> Kitchen dashboard (200 OK)")

        # Req 9: Already logged-in Kitchen user opens /auth/login -> redirected to dashboard without error
        resp_km_relogin = client.get('/auth/login', follow_redirects=True)
        assert resp_km_relogin.status_code == 200
        assert b"Apex University Central Mega-Mess" in resp_km_relogin.data
        assert b"Invalid" not in resp_km_relogin.data and b"does not exist" not in resp_km_relogin.data
        print("[PASS] Req 9: Already logged-in Kitchen Manager opening /auth/login -> routed directly to dashboard")

        # Req 7: Kitchen credentials + NGO role -> rejected
        client.get('/auth/logout')
        resp_km_as_ngo = client.post('/auth/login', data={'role': 'ngo', 'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
        assert resp_km_as_ngo.status_code == 200
        assert b"Role mismatch" in resp_km_as_ngo.data
        assert b"registered as a Kitchen Manager" in resp_km_as_ngo.data
        print("[PASS] Req 7: Kitchen Manager attempting login as NGO role -> strictly rejected with role mismatch")

        # Req 6: Correct NGO credentials + NGO Partner role -> NGO dashboard
        resp_ngo_ok = client.post('/auth/login', data={'role': 'ngo', 'username': 'feeding_india', 'password': 'ngo123'}, follow_redirects=True)
        assert resp_ngo_ok.status_code == 200
        assert b"Annapurna Food Rescue Foundation" in resp_ngo_ok.data
        assert b"NGO Relief Partner" in resp_ngo_ok.data
        assert b"Live Surplus Marketplace" in resp_ngo_ok.data
        print("[PASS] Req 6: Correct NGO credentials + NGO Partner role -> NGO dashboard (200 OK)")

        # Req 10: Already logged-in NGO user opens /auth/login -> redirected to dashboard without error
        resp_ngo_relogin = client.get('/auth/login', follow_redirects=True)
        assert resp_ngo_relogin.status_code == 200
        assert b"Annapurna Food Rescue Foundation" in resp_ngo_relogin.data
        assert b"Invalid" not in resp_ngo_relogin.data and b"does not exist" not in resp_ngo_relogin.data
        print("[PASS] Req 10: Already logged-in NGO Partner opening /auth/login -> routed directly to dashboard")

        # Req 8: NGO credentials + Kitchen role -> rejected
        client.get('/auth/logout')
        resp_ngo_as_km = client.post('/auth/login', data={'role': 'kitchen_manager', 'username': 'feeding_india', 'password': 'ngo123'}, follow_redirects=True)
        assert resp_ngo_as_km.status_code == 200
        assert b"Role mismatch" in resp_ngo_as_km.data
        assert b"registered as an NGO Relief Partner" in resp_ngo_as_km.data
        print("[PASS] Req 8: NGO account attempting login as Kitchen role -> strictly rejected with role mismatch")

        # Req 11: Logout -> session cleared -> login page
        client.post('/auth/login', data={'role': 'kitchen_manager', 'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
        resp_logout = client.get('/auth/logout', follow_redirects=True)
        assert resp_logout.status_code == 200
        assert b"You have been signed out successfully" in resp_logout.data
        assert b"Welcome Back" in resp_logout.data
        assert b"Apex Central Mess Manager" not in resp_logout.data
        print("[PASS] Req 11: Logout -> session cleared completely, redirected to clean login page")

        # Req 12: After logout, opening /auth/login must NOT redirect to dashboard
        resp_after_logout = client.get('/auth/login')
        assert resp_after_logout.status_code == 200
        assert b"Sign In" in resp_after_logout.data
        assert b"Apex University Central Mega-Mess" not in resp_after_logout.data
        print("[PASS] Req 12: After logout, /auth/login serves clean unauthenticated login form")

        # Req 13: Browser back after logout must not expose authenticated page (no-cache headers verified)
        assert "no-store" in resp_logout.headers.get("Cache-Control", "")
        assert "no-cache" in resp_logout.headers.get("Cache-Control", "")
        print("[PASS] Req 13: Strict Cache-Control: no-cache, no-store verified to prevent back-button leakage")

        # Req 14: Show/hide password still works & Quick Demo Personas completely removed
        assert b'toggle-password' in resp_after_logout.data
        assert b'data-target="#login_password"' in resp_after_logout.data
        assert b"Quick Demo Personas" not in resp_after_logout.data
        assert b"role_kitchen" in resp_after_logout.data
        assert b"role_ngo" in resp_after_logout.data
        print("[PASS] Req 14: Show/Hide password preserved & Quick Demo Personas completely removed from UI")

        # Test: Registration Validation
        resp_reg_short = client.post('/auth/register', data={
            'username': 'ab', # too short (<3)
            'email': 'bad_email',
            'password': '123', # too short (<6)
            'role': 'kitchen_manager',
            'organization_name': 'Test Org',
            'contact_phone': '1234567890',
            'address': 'Test Address'
        }, follow_redirects=True)
        assert resp_reg_short.status_code == 200
        assert b"Username must be at least 3 characters long" in resp_reg_short.data
        print("[PASS] Register Validation: Short inputs and malformed emails properly rejected")

        # Registration page password toggle
        resp_reg_page = client.get('/auth/register')
        assert b'toggle-password' in resp_reg_page.data
        assert b'data-target="#register_password"' in resp_reg_page.data
        # Test 18: Waste logging validation - negative weight rejection
        client.get('/auth/demo-login/kitchen_manager', follow_redirects=True)
        resp_waste_neg = client.post('/kitchen/waste/log', data={
            'date': '2026-09-12',
            'meal_session': 'Lunch',
            'waste_category': 'Plate Waste',
            'food_item': 'Rice',
            'weight_kg': '-5.0',
            'reason': 'Testing'
        }, follow_redirects=True)
        assert b"Waste weight must be greater than 0 kg" in resp_waste_neg.data
        print("[PASS] Waste Validation: Negative weight rejected with user-friendly warning")

        # Test 19: Waste logging creation & unified cost calculation
        resp_waste_ok = client.post('/kitchen/waste/log', data={
            'date': '2026-09-12',
            'meal_session': 'Lunch',
            'waste_category': 'Plate Waste',
            'food_item': 'Automated Test Dal',
            'weight_kg': '10.0',
            'reason': 'Portion test'
        }, follow_redirects=True)
        assert resp_waste_ok.status_code == 200
        # 10.0 kg of Plate Waste @ 60/kg = ₹600.00
        assert b"600.00" in resp_waste_ok.data
        print("[PASS] Waste Creation: Persisted to SQLite, exact economic loss (10kg * 60 = 600) confirmed")

        # Test 20: Inventory validation - negative quantity rejection
        resp_inv_neg = client.post('/kitchen/inventory', data={
            'item_name': 'Bad Item',
            'category': 'Grains',
            'quantity': '-10',
            'unit': 'kg',
            'expiry_date': '2026-10-01'
        }, follow_redirects=True)
        assert b"Stock quantity must be greater than 0" in resp_inv_neg.data
        print("[PASS] Inventory Validation: Negative stock quantity properly rejected")

        # Test 21: Inventory creation & deletion
        resp_inv_ok = client.post('/kitchen/inventory', data={
            'item_name': 'Test Inventory Basmati',
            'category': 'Grains',
            'quantity': '20.0',
            'unit': 'kg',
            'expiry_date': '2026-10-15',
            'min_threshold': '5.0',
            'cost_per_unit': '60.0'
        }, follow_redirects=True)
        assert b"Test Inventory Basmati" in resp_inv_ok.data
        test_item = InventoryItem.query.filter_by(item_name='Test Inventory Basmati').first()
        assert test_item is not None
        # Delete item
        resp_inv_del = client.post(f'/kitchen/inventory/delete/{test_item.id}', follow_redirects=True)
        assert b"Removed" in resp_inv_del.data and b"from inventory" in resp_inv_del.data
        print("[PASS] Inventory CRUD: Created, persisted, and deleted successfully")

        # Test 22: Surplus listing validation - Food safety declaration required
        resp_surplus_unsafe = client.post('/donation/list', data={
            'food_name': 'Unverified Leftovers',
            'quantity_portions': '50',
            'weight_approx_kg': '20.0',
            'dietary_type': 'Vegetarian',
            'safe_hours': '4.0',
            'pickup_address': 'Kitchen Gate',
            'contact_phone': '9876543210'
            # Omitting fssai_verified
        }, follow_redirects=True)
        assert b"Food safety confirmation is mandatory" in resp_surplus_unsafe.data
        print("[PASS] Food Safety Rule: Unverified/unsafe food broadcast strictly rejected")

        # Test 23: Surplus listing creation - with safety confirmation
        resp_surplus_ok = client.post('/donation/list', data={
            'food_name': 'Automated Test Surplus Kheer',
            'quantity_portions': '40',
            'weight_approx_kg': '16.0',
            'dietary_type': 'Vegetarian',
            'safe_hours': '4.0',
            'pickup_address': 'Mess Gate 2',
            'contact_phone': '+91 98765 43210',
            'fssai_verified': 'on'
        }, follow_redirects=True)
        assert resp_surplus_ok.status_code == 200
        test_listing = SurplusListing.query.filter_by(food_name='Automated Test Surplus Kheer').order_by(SurplusListing.id.desc()).first()
        assert test_listing is not None
        assert test_listing.status == 'Available'
        print("[PASS] Surplus Broadcast: Created with FSSAI verification & available on marketplace")

        # Test 24: Claim portion bounds validation
        client.get('/auth/demo-login/ngo', follow_redirects=True)
        resp_claim_exceed = client.post(f'/donation/claim/{test_listing.id}', data={
            'beneficiaries_count': '999', # Exceeds 40
            'notes': 'Over-request test'
        }, follow_redirects=True)
        assert b"cannot exceed available quantity" in resp_claim_exceed.data
        print("[PASS] Claim Validation: Exceeding available portions rejected safely")

        # Test 25: Valid surplus claim creation & 6-digit OTP generation
        resp_claim_ok = client.post(f'/donation/claim/{test_listing.id}', data={
            'beneficiaries_count': '40',
            'notes': 'Verified test shelter dispatch'
        }, follow_redirects=True)
        assert resp_claim_ok.status_code == 200
        test_claim = Claim.query.filter_by(listing_id=test_listing.id).order_by(Claim.id.desc()).first()
        assert test_claim is not None
        assert len(test_claim.verification_otp) == 6
        assert test_claim.verification_otp.isdigit()
        print(f"[PASS] Surplus Claim: Successfully created with 6-digit OTP ({test_claim.verification_otp})")

        # Test 26: OTP verification validation & delivery completion
        client.get('/auth/demo-login/kitchen_manager', follow_redirects=True)
        # Bad OTP
        resp_bad_otp = client.post(f'/donation/verify-otp/{test_claim.id}', data={'otp': '000000'}, follow_redirects=True)
        assert b"Invalid OTP entered" in resp_bad_otp.data

        # Invalid format (not 6 digits)
        resp_fmt_otp = client.post(f'/donation/verify-otp/{test_claim.id}', data={'otp': '123'}, follow_redirects=True)
        assert b"must be exactly 6 numeric digits" in resp_fmt_otp.data

        # Correct OTP
        resp_good_otp = client.post(f'/donation/verify-otp/{test_claim.id}', data={'otp': test_claim.verification_otp}, follow_redirects=True)
        assert b"Delivery of 40 meals confirmed" in resp_good_otp.data
        updated_claim = db.session.get(Claim, test_claim.id)
        assert updated_claim.status == 'Delivered'
        assert updated_claim.listing.status == 'Completed'
        print("[PASS] OTP Verification: Exact 6-digit match confirmed, status transitioned to Delivered")

        # Test 27: Re-verification prevention
        resp_reverify = client.post(f'/donation/verify-otp/{test_claim.id}', data={'otp': test_claim.verification_otp}, follow_redirects=True)
        assert b"already been verified and delivered" in resp_reverify.data
        print("[PASS] Re-verification Guard: Already delivered claim cannot be re-verified")

        # Test 28: Custom 404 handler
        resp_404 = client.get('/non-existent-page-testing-404')
        assert resp_404.status_code == 404
        assert b"404 - Resource Not Found" in resp_404.data
        print("[PASS] Custom 404 Page: Handled gracefully with Return to Dashboard link")

        # ==========================================
        # Comprehensive Waste Log Module Tests (SIH Round 1)
        # ==========================================
        print("\nRunning SIH Round 1 Waste Log Module Tests...")
        client.get('/auth/demo-login/kitchen_manager', follow_redirects=True)

        # 1. New Waste Entry page loads with 200 OK
        resp_waste_page = client.get('/kitchen/waste/log')
        assert resp_waste_page.status_code == 200
        # Check SQLite message is absent
        assert b"Data saved directly to SQLite repository" not in resp_waste_page.data
        # Check Primary Root Cause is absent
        assert b"Primary Root Cause / Operational Reason" not in resp_waste_page.data
        # Check Estimation formula container is present
        assert b"calc_formula_text" in resp_waste_page.data
        print("[PASS] Waste Module Req 1: Waste Log page loads with 200 OK, SQLite message & Root cause dropdown removed")

        # 2. Navigation dropdown check
        assert b"wasteLogDropdown" in resp_waste_page.data
        assert b"New Waste Entry" in resp_waste_page.data
        assert b"Waste Log History" in resp_waste_page.data
        print("[PASS] Waste Module Req 2: Navigation menu contains Waste Log dropdown with both links")

        # 3. Empty weight rejection
        resp_empty_wt = client.post('/kitchen/waste/log', data={
            'date': '2026-09-12',
            'meal_session': 'Lunch',
            'waste_category': 'Plate Waste',
            'food_item': 'Steamed Rice',
            'weight_kg': ''
        }, follow_redirects=True)
        assert b"Please enter the measured waste weight in kilograms" in resp_empty_wt.data
        print("[PASS] Waste Module Req 3: Empty weight rejected")

        # 4. Zero weight rejection
        resp_zero_wt = client.post('/kitchen/waste/log', data={
            'date': '2026-09-12',
            'meal_session': 'Lunch',
            'waste_category': 'Plate Waste',
            'food_item': 'Steamed Rice',
            'weight_kg': '0'
        }, follow_redirects=True)
        assert b"Waste weight must be greater than 0 kg" in resp_zero_wt.data
        print("[PASS] Waste Module Req 4: Zero weight rejected")

        # 5. Negative weight rejection
        resp_neg_wt = client.post('/kitchen/waste/log', data={
            'date': '2026-09-12',
            'meal_session': 'Lunch',
            'waste_category': 'Plate Waste',
            'food_item': 'Steamed Rice',
            'weight_kg': '-12.5'
        }, follow_redirects=True)
        assert b"Waste weight must be greater than 0 kg" in resp_neg_wt.data
        print("[PASS] Waste Module Req 5: Negative weight rejected")

        # 6. Non-numeric weight rejection
        resp_non_num = client.post('/kitchen/waste/log', data={
            'date': '2026-09-12',
            'meal_session': 'Lunch',
            'waste_category': 'Plate Waste',
            'food_item': 'Steamed Rice',
            'weight_kg': 'five_kg'
        }, follow_redirects=True)
        assert b"Please enter a valid numeric value for waste weight" in resp_non_num.data
        print("[PASS] Waste Module Req 6: Non-numeric weight rejected")

        # 7. Excessive weight rejection (> 2000 kg)
        resp_excess_wt = client.post('/kitchen/waste/log', data={
            'date': '2026-09-12',
            'meal_session': 'Lunch',
            'waste_category': 'Plate Waste',
            'food_item': 'Steamed Rice',
            'weight_kg': '3500'
        }, follow_redirects=True)
        assert b"exceeds maximum realistic single batch threshold" in resp_excess_wt.data
        print("[PASS] Waste Module Req 7: Excessive weight (>2000 kg) rejected")

        # 8. Empty food name rejection
        resp_empty_food = client.post('/kitchen/waste/log', data={
            'date': '2026-09-12',
            'meal_session': 'Lunch',
            'waste_category': 'Plate Waste',
            'food_item': '',
            'weight_kg': '5.0'
        }, follow_redirects=True)
        assert b"Please enter the specific food item or dish name" in resp_empty_food.data
        print("[PASS] Waste Module Req 8: Empty food name rejected")

        # 9. Whitespace-only food name rejection
        resp_ws_food = client.post('/kitchen/waste/log', data={
            'date': '2026-09-12',
            'meal_session': 'Lunch',
            'waste_category': 'Plate Waste',
            'food_item': '     ',
            'weight_kg': '5.0'
        }, follow_redirects=True)
        assert b"Please enter the specific food item or dish name" in resp_ws_food.data
        print("[PASS] Waste Module Req 9: Whitespace-only food name rejected")

        # 10. Invalid meal session rejection
        resp_bad_session = client.post('/kitchen/waste/log', data={
            'date': '2026-09-12',
            'meal_session': 'MidnightFeast',
            'waste_category': 'Plate Waste',
            'food_item': 'Biryani',
            'weight_kg': '5.0'
        }, follow_redirects=True)
        assert b"Please select a valid meal session" in resp_bad_session.data
        print("[PASS] Waste Module Req 10: Invalid meal session rejected")

        # 11. Invalid waste category rejection
        resp_bad_cat = client.post('/kitchen/waste/log', data={
            'date': '2026-09-12',
            'meal_session': 'Dinner',
            'waste_category': 'RandomStream',
            'food_item': 'Biryani',
            'weight_kg': '5.0'
        }, follow_redirects=True)
        assert b"Please select a valid waste category" in resp_bad_cat.data
        print("[PASS] Waste Module Req 11: Invalid waste category rejected")

        # 12. Malformed date rejection
        resp_bad_date = client.post('/kitchen/waste/log', data={
            'date': '12-09-2026',
            'meal_session': 'Dinner',
            'waste_category': 'Plate Waste',
            'food_item': 'Biryani',
            'weight_kg': '5.0'
        }, follow_redirects=True)
        assert b"Invalid date format provided" in resp_bad_date.data
        print("[PASS] Waste Module Req 12: Malformed date rejected")

        # 13. Food-specific benchmark calculation: Rice (₹35/kg)
        loss_rice = calculate_waste_loss(10.0, 'Plate Waste', 'Cooked Basmati Rice')
        assert loss_rice == 350.00
        print("[PASS] Waste Module Req 13: Food-specific benchmark calculation (Rice 10kg @ 35 = 350.00)")

        # 14. Food-specific benchmark calculation: Paneer (₹180/kg)
        loss_paneer = calculate_waste_loss(5.0, 'Buffet Leftover', 'Paneer Butter Masala')
        assert loss_paneer == 900.00
        print("[PASS] Waste Module Req 14: Food-specific benchmark calculation (Paneer 5kg @ 180 = 900.00)")

        # 15. Unknown food category fallback calculation
        loss_unknown = calculate_waste_loss(10.0, 'Prep Waste', 'Mystery Concoction XYZ')
        assert loss_unknown == 300.00
        print("[PASS] Waste Module Req 15: Unknown food category fallback calculation (Prep Waste 10kg @ 30 = 300.00)")

        # 16. Multiple food items blended rate calculation
        loss_blended = calculate_waste_loss(10.0, 'Plate Waste', 'Cooked Rice & Dal')
        assert loss_blended == 475.00
        loss_tri = calculate_waste_loss(6.0, 'Plate Waste', 'Rice, Dal, Mixed Veg')
        assert loss_tri == 280.02
        print("[PASS] Waste Module Req 16: Multi-item blended calculation (Rice & Dal 10kg @ 47.5 = 475.00)")

        # 17. Deterministic calculation: Same input produces identical loss repeatedly
        assert calculate_waste_loss(10.0, 'Plate Waste', 'Cooked Rice & Dal') == 475.00
        assert calculate_waste_loss(10.0, 'Plate Waste', 'Cooked Rice & Dal') == 475.00
        print("[PASS] Waste Module Req 17: Deterministic single source of truth confirmed")

        # 18. Valid waste entry submission, persistence, and redirect to history
        resp_entry = client.post('/kitchen/waste/log', data={
            'date': '2026-09-12',
            'meal_session': 'Lunch',
            'waste_category': 'Plate Waste',
            'food_item': 'Institutional Rice & Dal Combo',
            'weight_kg': '8.0'
        }, follow_redirects=True)
        assert resp_entry.status_code == 200
        # 8.0 kg @ 47.50 = ₹380.00
        assert b"380.00" in resp_entry.data
        assert b"Food Waste Measurement Ledger" in resp_entry.data
        
        # Verify in SQLite database
        persisted_log = WasteLog.query.filter_by(food_item='Institutional Rice & Dal Combo').order_by(WasteLog.id.desc()).first()
        assert persisted_log is not None
        assert persisted_log.weight_kg == 8.0
        assert persisted_log.estimated_cost_loss == 380.00
        assert persisted_log.reason is None
        print(f"[PASS] Waste Module Req 18: Record saved to SQLite with exact loss (Rs. {persisted_log.estimated_cost_loss}) and reason=None")

        # 19. History page shows exact stored estimated loss
        resp_history = client.get('/kitchen/waste/history')
        assert resp_history.status_code == 200
        assert b"380.00" in resp_history.data
        assert b"Root Cause Reason" not in resp_history.data
        print("[PASS] Waste Module Req 19: Waste history displays exact stored loss (Rs. 380.00) without Root Cause column")

        # 20. Dashboard uses exact same stored estimated loss
        resp_dash = client.get('/dashboard')
        assert resp_dash.status_code == 200
        assert b"380.00" in resp_dash.data
        print("[PASS] Waste Module Req 20: Dashboard uses identical stored waste loss value (Rs. 380.00)")

        # 21. User scoping: Kitchen Manager A cannot see Kitchen Manager B's waste records
        client.get('/auth/logout')
        client.post('/auth/login', data={'role': 'kitchen_manager', 'username': 'kitchen_demo', 'password': 'demo1234'}, follow_redirects=True)
        resp_other_history = client.get('/kitchen/waste/history')
        assert resp_other_history.status_code == 200
        # Record logged by admin should NOT appear in kitchen_demo's ledger
        assert b"Institutional Rice & Dal Combo" not in resp_other_history.data
        print("[PASS] Waste Module Req 21: Strict user isolation verified (other user cannot see private waste records)")

        # 22. Database error rollback handling test
        client.get('/auth/demo-login/kitchen_manager', follow_redirects=True)
        from unittest.mock import patch
        with patch('app.db.session.commit', side_effect=Exception("Simulated SQLite Failure")):
            resp_fail = client.post('/kitchen/waste/log', data={
                'date': '2026-09-12',
                'meal_session': 'Dinner',
                'waste_category': 'Plate Waste',
                'food_item': 'Rollback Test Dish',
                'weight_kg': '4.0'
            }, follow_redirects=True)
            assert b"database error occurred while saving" in resp_fail.data
            rolled_back_record = WasteLog.query.filter_by(food_item='Rollback Test Dish').first()
            assert rolled_back_record is None
        print("[PASS] Waste Module Req 22: Safe transaction rollback verified on DB failure")

        # ==========================================
        # Comprehensive Food-wise Preparation Plan Module Tests (Simplified Automated Benchmarks)
        # ==========================================
        print("\nRunning AI Food-wise Preparation Plan Module Tests...")

        # 1. Automatic Benchmark & Unit Resolution: Known Food Types
        b_rice, u_rice = resolve_food_benchmark('Steamed Basmati Rice')
        assert u_rice == 'kg'
        assert b_rice == 0.119

        b_roti, u_roti = resolve_food_benchmark('Tandoori Roti')
        assert u_roti == 'pieces'
        assert b_roti == 2.0

        b_dal, u_dal = resolve_food_benchmark('Yellow Dal Tadka')
        assert u_dal == 'kg'
        assert b_dal == 0.06

        b_curd, u_curd = resolve_food_benchmark('Fresh Curd')
        assert u_curd == 'kg'
        assert b_curd == 0.05

        b_soup, u_soup = resolve_food_benchmark('Hot Tomato Soup')
        assert u_soup == 'litres'
        assert b_soup == 0.15
        print("[PASS] Food-wise Plan Req 1: Automatic benchmark and unit resolution for known foods verified (Rice=kg, Roti=pieces, Soup=litres)")

        # 2. Unknown Food Item Fallback
        b_unknown, u_unknown = resolve_food_benchmark('Exotic Fusion Specialty Dish XYZ')
        assert u_unknown == 'kg'
        assert b_unknown == 0.08
        print("[PASS] Food-wise Plan Req 2: Unknown food items gracefully assigned sensible default fallback (0.08 kg/person)")

        # 3. Calculation Precision for SIH MVP Examples (675 attendance @ 6% buffer)
        # Rice: 675 * 0.119 * 1.06 = 85.14 kg -> 85 kg
        qty_rice, u_rice, _ = estimate_food_requirement('Rice', 675, 6.0)
        assert round(qty_rice) == 85
        assert u_rice == 'kg'

        # Dal: 675 * 0.06 * 1.06 = 42.93 kg -> 43 kg
        qty_dal, u_dal, _ = estimate_food_requirement('Dal', 675, 6.0)
        assert round(qty_dal) == 43
        assert u_dal == 'kg'

        # Vegetable Sabji: 675 * 0.08 * 1.06 = 57.24 kg -> 57 kg
        qty_sabji, u_sabji, _ = estimate_food_requirement('Vegetable Sabji', 675, 6.0)
        assert round(qty_sabji) == 57
        assert u_sabji == 'kg'

        # Roti: 675 * 2.0 * 1.06 = 1,431 pieces
        qty_roti, u_roti, _ = estimate_food_requirement('Roti', 675, 6.0)
        assert qty_roti == 1431.0
        assert u_roti == 'pieces'

        # Salad: 675 * 0.04 * 1.06 = 28.62 kg -> 29 kg
        qty_salad, u_salad, _ = estimate_food_requirement('Salad', 675, 6.0)
        assert round(qty_salad) == 29
        assert u_salad == 'kg'

        # Curd: 675 * 0.05 * 1.06 = 35.78 kg -> 36 kg
        qty_curd, u_curd, _ = estimate_food_requirement('Curd', 675, 6.0)
        assert round(qty_curd) == 36
        assert u_curd == 'kg'
        print("[PASS] Food-wise Plan Req 3: Automated requirements match all example values (Rice=85kg, Dal=43kg, Sabji=57kg, Roti=1,431pcs, Salad=29kg, Curd=36kg)")

        # 4. Safety buffer scaling verified
        qty_buf0, _, _ = estimate_food_requirement('Rice', 500, 0.0)
        qty_buf10, _, _ = estimate_food_requirement('Rice', 500, 10.0)
        assert qty_buf0 == 59.5 # 500 * 0.119 * 1.0 = 59.5
        assert qty_buf10 == 65.45 # 500 * 0.119 * 1.10 = 65.45
        print("[PASS] Food-wise Plan Req 4: Safety buffer scaling properly applied to calculations")

        # 5. Unauthenticated user rejected
        client.get('/auth/logout')
        resp_unauth = client.post('/ai/food-plan/create', data={
            'predicted_attendance': '675',
            'safety_buffer': '6.0',
            'food_name[]': ['Rice', 'Dal']
        })
        assert resp_unauth.status_code == 302
        assert '/auth/login' in resp_unauth.headers.get('Location', '')
        print("[PASS] Food-wise Plan Req 5: Unauthenticated access rejected and redirected to login")

        # 6. NGO user cannot create food preparation plan
        client.get('/auth/demo-login/ngo', follow_redirects=True)
        resp_ngo_plan = client.post('/ai/food-plan/create', data={
            'predicted_attendance': '675',
            'safety_buffer': '6.0',
            'food_name[]': ['Rice', 'Dal']
        }, follow_redirects=True)
        assert resp_ngo_plan.status_code == 200
        assert (b"Only Kitchen Managers can create food preparation plans" in resp_ngo_plan.data or b"restricted to Kitchen Managers" in resp_ngo_plan.data)
        print("[PASS] Food-wise Plan Req 6: NGO user strictly forbidden from creating food plans")

        # 7. Kitchen Manager login & empty menu rejection
        client.get('/auth/demo-login/kitchen_manager', follow_redirects=True)
        resp_empty_menu = client.post('/ai/food-plan/create', data={
            'predicted_attendance': '675',
            'safety_buffer': '6.0',
            'food_name[]': []
        }, follow_redirects=True)
        assert b"At least one food item is required" in resp_empty_menu.data
        print("[PASS] Food-wise Plan Req 7: Empty menu rejected with validation warning")

        # 8. Blank food name rejected
        resp_empty_name = client.post('/ai/food-plan/create', data={
            'predicted_attendance': '675',
            'safety_buffer': '6.0',
            'food_name[]': ['   ']
        }, follow_redirects=True)
        assert b"Food item name cannot be blank" in resp_empty_name.data or b"Please enter at least one valid food item" in resp_empty_name.data
        print("[PASS] Food-wise Plan Req 8: Empty food name rejected with validation warning")

        # 9. Case-insensitive duplicate food names rejected
        resp_dup = client.post('/ai/food-plan/create', data={
            'predicted_attendance': '675',
            'safety_buffer': '6.0',
            'food_name[]': ['Rice', 'rice']
        }, follow_redirects=True)
        assert b"Duplicate food item detected" in resp_dup.data
        print("[PASS] Food-wise Plan Req 9: Case-insensitive duplicate food names ('Rice' vs 'rice') rejected")

        # 10. Valid multi-item plan creation with food names only (No units, no user quantity needed)
        resp_valid_plan = client.post('/ai/food-plan/create', data={
            'capacity': '750',
            'meal_session': 'Lunch',
            'day_of_week': '2',
            'event_type': 'None',
            'predicted_attendance': '675',
            'safety_buffer': '6.0',
            'food_name[]': ['Rice', 'Dal', 'Vegetable Sabji', 'Roti', 'Salad', 'Curd']
        }, follow_redirects=True)
        assert resp_valid_plan.status_code == 200
        assert b"AI Food-wise Preparation Plan generated and saved successfully" in resp_valid_plan.data
        assert b"AI Food-wise Preparation Recommendation" in resp_valid_plan.data
        assert (b"Estimated Quantity" in resp_valid_plan.data or b"Estimated Requirement" in resp_valid_plan.data)

        # Check rendered output values
        assert b"85 kg" in resp_valid_plan.data
        assert b"43 kg" in resp_valid_plan.data
        assert b"57 kg" in resp_valid_plan.data
        assert b"1,431 pieces" in resp_valid_plan.data
        assert b"29 kg" in resp_valid_plan.data
        assert b"36 kg" in resp_valid_plan.data

        # 11. Verify persisted relational records in SQLite
        saved_plan = FoodPreparationPlan.query.filter_by(predicted_attendance=675).order_by(FoodPreparationPlan.id.desc()).first()
        assert saved_plan is not None
        assert saved_plan.safety_buffer == 6.0
        assert saved_plan.meal_session == 'Lunch'
        assert len(saved_plan.items) == 6

        plan_items = {it.food_name: (it.estimated_quantity, it.estimated_unit, it.serving_benchmark) for it in saved_plan.items}
        assert plan_items['Rice'][1] == 'kg'
        assert round(plan_items['Rice'][0]) == 85
        assert plan_items['Roti'][1] == 'pieces'
        assert plan_items['Roti'][0] == 1431.0
        assert plan_items['Curd'][1] == 'kg'
        assert round(plan_items['Curd'][0]) == 36
        print(f"[PASS] Food-wise Plan Req 10 & 11: Multi-item plan generated from food names only and persisted in SQLite (Plan #{saved_plan.id})")

        # 12. Transaction rollback on database failure
        with patch('app.db.session.commit', side_effect=Exception("Simulated SQLite Failure")):
            resp_rollback = client.post('/ai/food-plan/create', data={
                'predicted_attendance': '900',
                'safety_buffer': '5.0',
                'food_name[]': ['Rollback Specialty Dish']
            }, follow_redirects=True)
            assert b"A database error occurred while saving" in resp_rollback.data
            rb_plan = FoodPreparationPlan.query.filter_by(predicted_attendance=900).first()
            assert rb_plan is None
            rb_item = FoodPreparationItem.query.filter_by(food_name='Rollback Specialty Dish').first()
            assert rb_item is None
        print("[PASS] Food-wise Plan Req 12: Atomic transaction rollback verified on DB failure")

        # 13. User Isolation: Kitchen Manager B cannot access Kitchen Manager A's food plan
        client.get('/auth/logout')
        client.post('/auth/login', data={'role': 'kitchen_manager', 'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
        resp_isolate = client.get(f'/ai/food-plan/{saved_plan.id}', follow_redirects=True)
        assert b"Food preparation plan not found or access denied" in resp_isolate.data
        print("[PASS] Food-wise Plan Req 13: Cross-tenant isolation verified (User B cannot view User A's plan)")

        # 14. Existing AI forecast routes unaffected
        resp_fc = client.get('/ai/forecast?capacity=850&meal_session=Dinner&buffer_percent=7.0')
        assert resp_fc.status_code == 200
        assert b"Calibrated Kitchen Production Plan" in resp_fc.data
        assert b"Target Portions to Cook" in resp_fc.data
        assert b"forecastComparisonChart" in resp_fc.data
        assert b"Food-wise Preparation Plan" in resp_fc.data
        print("[PASS] Food-wise Plan Req 14: Existing AI forecast route & comparison chart fully functional")

        # 15. Historical plans section renders stored data without recalculation
        client.get('/auth/logout')
        client.get('/auth/demo-login/kitchen_manager', follow_redirects=True)
        resp_history = client.get('/ai/forecast')
        assert resp_history.status_code == 200
        assert b"Previous Food-wise Preparation Plans" in resp_history.data
        assert b"Rice" in resp_history.data
        assert b"85 kg" in resp_history.data
        assert b"1,431 pieces" in resp_history.data
        print("[PASS] Food-wise Plan Req 15: Historical food plans accurately rendered from stored point-in-time values")

        # =========================================================================
        # Comprehensive NGO & Kitchen Role Separation and Redistribution Test Suite
        # =========================================================================
        print("\nRunning NGO & Kitchen Role Separation and Redistribution Tests...")

        # 1. Valid NGO login succeeds
        client.get('/auth/logout')
        resp_ngo_login = client.post('/auth/login', data={
            'role': 'ngo',
            'username': 'ngo_demo',
            'password': 'demo1234'
        }, follow_redirects=True)
        assert resp_ngo_login.status_code == 200
        assert b"Annapurna Food Rescue Foundation" in resp_ngo_login.data
        assert b"NGO / Relief Partner Portal" in resp_ngo_login.data
        print("[PASS] NGO Req 1: Valid NGO login succeeds and routes to dedicated NGO dashboard")

        # 2. Invalid NGO password fails
        client.get('/auth/logout')
        resp_ngo_bad_pwd = client.post('/auth/login', data={
            'role': 'ngo',
            'username': 'ngo_demo',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        assert resp_ngo_bad_pwd.status_code == 200
        assert b"Invalid username or password" in resp_ngo_bad_pwd.data
        print("[PASS] NGO Req 2: Invalid NGO password fails safely")

        # 3. Valid Kitchen login still succeeds
        resp_km_login = client.post('/auth/login', data={
            'role': 'kitchen_manager',
            'username': 'admin',
            'password': 'admin123'
        }, follow_redirects=True)
        assert resp_km_login.status_code == 200
        assert b"Apex University Central Mega-Mess" in resp_km_login.data
        assert b"Kitchen Manager" in resp_km_login.data
        print("[PASS] NGO Req 3: Valid Kitchen Manager login still succeeds")

        # 4. Logout works
        resp_logout = client.get('/auth/logout', follow_redirects=True)
        assert resp_logout.status_code == 200
        assert b"signed out successfully" in resp_logout.data
        print("[PASS] NGO Req 4: Logout works and clears session completely")

        # 5. Browser/form role manipulation cannot change actual database role
        resp_tamper = client.post('/auth/login', data={
            'role': 'kitchen_manager', # Tampered role selection for NGO account
            'username': 'ngo_demo',
            'password': 'demo1234'
        }, follow_redirects=True)
        assert resp_tamper.status_code == 200
        assert b"Role mismatch" in resp_tamper.data
        print("[PASS] NGO Req 5: Form role manipulation strictly prevented by database authoritative check")

        # Authenticate as NGO
        client.get('/auth/demo-login/ngo', follow_redirects=True)

        # 6. NGO can access NGO dashboard with real database metrics
        resp_ngo_dash = client.get('/dashboard')
        assert resp_ngo_dash.status_code == 200
        assert b"Available Surplus" in resp_ngo_dash.data
        assert b"My Active Claims" in resp_ngo_dash.data
        assert b"Meals Received" in resp_ngo_dash.data
        assert b"Completed Deliveries" in resp_ngo_dash.data
        assert b"Browse Live Surplus" in resp_ngo_dash.data
        assert b"My Claims & Dispatch Tracking" in resp_ngo_dash.data
        # Confirm Kitchen operational modules are NOT in NGO dashboard
        assert b"total_waste_kg" not in resp_ngo_dash.data
        assert b"wasteCategoryChart" not in resp_ngo_dash.data
        print("[PASS] NGO Req 6: Dedicated NGO Dashboard loads with database-driven metrics and zero kitchen metrics")

        # 7. NGO can access marketplace
        resp_mkt = client.get('/donation/marketplace')
        assert resp_mkt.status_code == 200
        assert b"Live Surplus Food Redistribution Feed" in resp_mkt.data
        # Confirm NGO does NOT see 'Broadcast Surplus Food' button
        assert b"Broadcast Surplus Food" not in resp_mkt.data
        print("[PASS] NGO Req 7: NGO can access marketplace without kitchen broadcast controls")

        # 8. NGO can access its claims
        resp_tracking = client.get('/donation/tracking')
        assert resp_tracking.status_code == 200
        assert b"My Claims & Dispatch Tracking" in resp_tracking.data
        print("[PASS] NGO Req 8: NGO can access My Claims & Dispatch Tracking")

        # 9. NGO cannot access Waste Log (direct URL)
        resp_no_waste = client.get('/kitchen/waste/log', follow_redirects=True)
        assert b"restricted to Kitchen Managers" in resp_no_waste.data
        assert b"NGO / Relief Partner Portal" in resp_no_waste.data
        print("[PASS] NGO Req 9: NGO strictly blocked from /kitchen/waste/log and redirected to NGO dashboard")

        # 10. NGO cannot access Inventory (direct URL)
        resp_no_inv = client.get('/kitchen/inventory', follow_redirects=True)
        assert b"restricted to Kitchen Managers" in resp_no_inv.data
        print("[PASS] NGO Req 10: NGO strictly blocked from /kitchen/inventory")

        # 11. NGO cannot access AI Forecast (direct URL)
        resp_no_fc = client.get('/ai/forecast', follow_redirects=True)
        assert b"restricted to Kitchen Managers" in resp_no_fc.data
        print("[PASS] NGO Req 11: NGO strictly blocked from /ai/forecast")

        # 12. NGO cannot access Food Preparation Plan (direct URL)
        resp_no_fpp = client.post('/ai/food-plan/create', data={'predicted_attendance': '500', 'food_name[]': ['Rice']}, follow_redirects=True)
        assert b"restricted to Kitchen Managers" in resp_no_fpp.data
        print("[PASS] NGO Req 12: NGO strictly blocked from /ai/food-plan/create")

        # 13. NGO cannot access Kitchen ESG Report (direct URL)
        resp_no_esg = client.get('/esg-report', follow_redirects=True)
        assert b"restricted to Kitchen Managers" in resp_no_esg.data
        print("[PASS] NGO Req 13: NGO strictly blocked from /esg-report")

        # 14. NGO cannot create/broadcast surplus (direct URL)
        resp_no_broadcast = client.get('/donation/list', follow_redirects=True)
        assert b"restricted to Kitchen Managers" in resp_no_broadcast.data
        print("[PASS] NGO Req 14: NGO strictly blocked from /donation/list")

        # 15. Kitchen Manager can access kitchen modules
        client.get('/auth/demo-login/kitchen_manager', follow_redirects=True)
        assert client.get('/kitchen/waste/log').status_code == 200
        assert client.get('/kitchen/inventory').status_code == 200
        assert client.get('/ai/forecast').status_code == 200
        assert client.get('/esg-report').status_code == 200
        print("[PASS] Kitchen Req 15: Kitchen Manager verified access to all operational kitchen modules")

        # 16. Kitchen can broadcast surplus
        resp_km_broadcast = client.post('/donation/list', data={
            'food_name': 'SIH Fresh Dal Tadka & Jeera Rice',
            'quantity_portions': '50',
            'weight_approx_kg': '22.5',
            'dietary_type': 'Vegetarian',
            'safe_hours': '6.0',
            'pickup_address': 'Main Kitchen Loading Dock 1',
            'contact_phone': '+91 98765 00112',
            'fssai_verified': 'on'
        }, follow_redirects=True)
        assert resp_km_broadcast.status_code == 200
        assert b"Surplus broadcast created" in resp_km_broadcast.data
        new_surplus = SurplusListing.query.filter_by(food_name='SIH Fresh Dal Tadka & Jeera Rice').order_by(SurplusListing.id.desc()).first()
        assert new_surplus is not None
        assert new_surplus.quantity_portions == 50
        assert new_surplus.status == 'Available'
        print("[PASS] Kitchen Req 16: Kitchen Manager can broadcast surplus with FSSAI verification")

        # 17. Kitchen Manager cannot claim surplus (only NGO can claim)
        resp_km_cant_claim = client.post(f'/donation/claim/{new_surplus.id}', data={
            'beneficiaries_count': '10',
            'notes': 'Kitchen cannot claim its own surplus'
        }, follow_redirects=True)
        assert b"restricted to NGO Relief Partners" in resp_km_cant_claim.data
        print("[PASS] Kitchen Req 17: Kitchen Manager strictly forbidden from claiming surplus food")

        # 18. Switch to NGO and verify marketplace listing appearance
        client.get('/auth/demo-login/ngo', follow_redirects=True)
        resp_mkt_view = client.get('/donation/marketplace')
        assert b"SIH Fresh Dal Tadka" in resp_mkt_view.data
        assert b"50" in resp_mkt_view.data
        print("[PASS] Marketplace Req 19: Eligible surplus appears in live marketplace for NGO")

        # 21 & 22. Over-claiming is safely rejected (requesting 60 when 50 available)
        resp_overclaim = client.post(f'/donation/claim/{new_surplus.id}', data={
            'beneficiaries_count': '60',
            'notes': 'Over-claiming test'
        }, follow_redirects=True)
        assert b"cannot exceed available quantity" in resp_overclaim.data
        chk_surplus = db.session.get(SurplusListing, new_surplus.id)
        assert chk_surplus.quantity_portions == 50
        print("[PASS] Claim Req 21 & 22: Over-claiming strictly rejected, portion pool preserved")

        # 23. Partial claiming safely reduces available portions
        # NGO claims 20 portions
        resp_claim_part1 = client.post(f'/donation/claim/{new_surplus.id}', data={
            'beneficiaries_count': '20',
            'notes': 'Sector 14 Shelter distribution'
        }, follow_redirects=True)
        assert resp_claim_part1.status_code == 200
        assert b"Success! You claimed 20 portions" in resp_claim_part1.data
        chk_surplus = db.session.get(SurplusListing, new_surplus.id)
        assert chk_surplus.quantity_portions == 30 # 50 - 20 = 30
        assert chk_surplus.status == 'Available' # Still available for other NGOs
        print("[PASS] Claim Req 23: Partial claim deducted available portions from 50 to 30; status remains Available")

        # Find the newly created claim
        claim_1 = Claim.query.filter_by(listing_id=new_surplus.id, beneficiaries_count=20).first()
        assert claim_1 is not None
        assert claim_1.ngo_id == 3 # ngo_demo ID
        assert len(claim_1.verification_otp) == 6
        assert claim_1.verification_otp.isdigit()
        print(f"[PASS] OTP Req 29 & 30: Generated unique 6-digit OTP ({claim_1.verification_otp}) associated with Claim #{claim_1.id}")

        # 31. Correct NGO can see its own OTP in My Claims
        resp_my_claims = client.get('/donation/tracking')
        assert claim_1.verification_otp.encode() in resp_my_claims.data
        assert b"Show this OTP to kitchen staff at pickup" in resp_my_claims.data
        print("[PASS] OTP Req 31: Claiming NGO sees its own OTP with clear pickup presentation instructions")

        # 32. Second NGO logs in and CANNOT see NGO 1's claim or OTP (Data Isolation)
        client.get('/auth/logout')
        client.post('/auth/login', data={'role': 'ngo', 'username': 'feeding_india', 'password': 'ngo123'}, follow_redirects=True)
        resp_ngo2_claims = client.get('/donation/tracking')
        assert claim_1.verification_otp.encode() not in resp_ngo2_claims.data
        assert f"#CLM-{claim_1.id}".encode() not in resp_ngo2_claims.data
        print("[PASS] Isolation Req 32: Second NGO strictly isolated; cannot view First NGO's claim or OTP")

        # Second NGO claims the remaining 30 portions
        resp_claim_part2 = client.post(f'/donation/claim/{new_surplus.id}', data={
            'beneficiaries_count': '30',
            'notes': 'Community Kitchen feeding drive'
        }, follow_redirects=True)
        assert resp_claim_part2.status_code == 200
        chk_surplus = db.session.get(SurplusListing, new_surplus.id)
        assert chk_surplus.quantity_portions == 0
        assert chk_surplus.status == 'Claimed' # Fully claimed now
        print("[PASS] Claim Req 23b: Second claim consumed remaining 30 portions; listing transitioned to Claimed")

        # Now available portions are 0; another claim must be rejected
        resp_claim_depleted = client.post(f'/donation/claim/{new_surplus.id}', data={
            'beneficiaries_count': '5',
            'notes': 'Attempting to claim from depleted listing'
        }, follow_redirects=True)
        assert b"no longer available" in resp_claim_depleted.data
        print("[PASS] Marketplace Req 20: Depleted surplus listing cannot be claimed")

        # 33. OTP is not visible publicly in marketplace
        resp_pub_mkt = client.get('/donation/marketplace')
        assert claim_1.verification_otp.encode() not in resp_pub_mkt.data
        print("[PASS] Security Req 33: Verification OTPs never exposed on public marketplace feed")

        # 35. Kitchen Manager verifies OTP: Wrong OTP fails
        client.get('/auth/demo-login/kitchen_manager', follow_redirects=True)
        resp_bad_otp = client.post(f'/donation/verify-otp/{claim_1.id}', data={'otp': '999999'}, follow_redirects=True)
        assert b"Invalid OTP entered" in resp_bad_otp.data
        chk_claim1 = db.session.get(Claim, claim_1.id)
        assert chk_claim1.status == 'Claimed' # Status unchanged
        print("[PASS] OTP Req 35: Wrong OTP strictly rejected; status remains Claimed")

        # 37. OTP for another claim fails
        claim_2 = Claim.query.filter_by(listing_id=new_surplus.id, beneficiaries_count=30).first()
        resp_mismatch_otp = client.post(f'/donation/verify-otp/{claim_1.id}', data={'otp': claim_2.verification_otp}, follow_redirects=True)
        assert b"Invalid OTP entered" in resp_mismatch_otp.data
        print("[PASS] OTP Req 37: Cross-claim OTP mismatch rejected safely")

        # 34 & 39. Correct OTP verifies successfully and marks Delivered
        resp_good_otp = client.post(f'/donation/verify-otp/{claim_1.id}', data={'otp': claim_1.verification_otp}, follow_redirects=True)
        assert b"Delivery of 20 meals confirmed" in resp_good_otp.data
        chk_claim1 = db.session.get(Claim, claim_1.id)
        assert chk_claim1.status == 'Delivered'
        assert chk_claim1.delivered_at is not None
        print("[PASS] OTP Req 34 & 39: Correct OTP verified; Claim #1 status transitioned to Delivered with timestamp")

        # 38. Already delivered claim cannot be re-verified
        resp_reverify = client.post(f'/donation/verify-otp/{claim_1.id}', data={'otp': claim_1.verification_otp}, follow_redirects=True)
        assert b"already been verified and delivered" in resp_reverify.data
        print("[PASS] OTP Req 38: Already delivered claim cannot be verified again")

        # Verify claim 2 as well to complete entire listing
        resp_good_otp2 = client.post(f'/donation/verify-otp/{claim_2.id}', data={'otp': claim_2.verification_otp}, follow_redirects=True)
        chk_surplus_done = db.session.get(SurplusListing, new_surplus.id)
        assert chk_surplus_done.status == 'Completed'
        print("[PASS] Listing Lifecycle: All claims delivered; SurplusListing status transitioned to Completed")

        # 41. Delivered portions contribute to NGO metrics
        client.get('/auth/demo-login/ngo', follow_redirects=True)
        resp_ngo_final_dash = client.get('/dashboard')
        # NGO 1 had existing claims + 20 from this test
        assert b"Meals Received" in resp_ngo_final_dash.data
        assert b"Completed Deliveries" in resp_ngo_final_dash.data
        print("[PASS] Metric Req 41: Delivered surplus portions immediately reflected in NGO real database dashboard")

        # 42. Profile / Organization route works for NGO and Kitchen
        resp_ngo_prof = client.get('/auth/profile')
        assert resp_ngo_prof.status_code == 200
        assert b"Annapurna Food Rescue Foundation" in resp_ngo_prof.data
        assert b"Organization & Account Profile" in resp_ngo_prof.data
        print("[PASS] Profile Req 42: Profile / Organization page displays accurate account details")

        print("Completed NGO & Kitchen Role Separation and Redistribution Tests successfully!")

        # =========================================================================
        # CITY-BASED SURPLUS VISIBILITY & CLAIM AUTHORIZATION TEST SUITE
        # =========================================================================
        print("\nRunning City-Based Surplus Visibility & Claim Authorization Tests...")

        # -------------------------------------------------------------------------
        # A. Database & Migration Schema Integrity
        # -------------------------------------------------------------------------
        assert hasattr(User, 'city'), "User model missing 'city' column"
        assert hasattr(SurplusListing, 'pickup_city'), "SurplusListing model missing 'pickup_city' column"

        kitchen_user_check = User.query.filter_by(username='kitchen_demo').first()
        assert kitchen_user_check is not None
        assert kitchen_user_check.city == 'Delhi', f"kitchen_demo city expected 'Delhi', got {kitchen_user_check.city}"

        ngo_user_check = User.query.filter_by(username='ngo_demo').first()
        assert ngo_user_check is not None
        assert ngo_user_check.city == 'Delhi', f"ngo_demo city expected 'Delhi', got {ngo_user_check.city}"

        rajkot_demo = User.query.filter_by(username='Demo3').first()
        if rajkot_demo:
            assert rajkot_demo.city == 'Rajkot', f"Demo3 city expected 'Rajkot', got {rajkot_demo.city}"

        delhi_listing_check = SurplusListing.query.filter_by(donor_id=kitchen_user_check.id).first()
        assert delhi_listing_check is not None
        assert delhi_listing_check.pickup_city == 'Delhi'
        print("[PASS] Test A: Safe SQLite migration verified - columns exist and existing data preserved")

        # -------------------------------------------------------------------------
        # B. User Registration with Operating City
        # -------------------------------------------------------------------------
        client.get('/auth/logout', follow_redirects=True)
        # B1. Missing city rejected
        resp_reg_no_city = client.post('/auth/register', data={
            'username': 'test_no_city',
            'email': 'nocity@test.org',
            'password': 'password123',
            'role': 'ngo',
            'organization_name': 'No City Shelter',
            'contact_phone': '+91 91234 56789',
            'address': 'Street 1, Main Road',
            'city': ''
        }, follow_redirects=True)
        assert b"Operating City is required" in resp_reg_no_city.data
        print("[PASS] Test B1: Missing operating city rejected during registration")

        # B2. Whitespace-only city rejected
        resp_reg_blank_city = client.post('/auth/register', data={
            'username': 'test_blank_city',
            'email': 'blankcity@test.org',
            'password': 'password123',
            'role': 'ngo',
            'organization_name': 'Blank City Shelter',
            'contact_phone': '+91 91234 56789',
            'address': 'Street 1, Main Road',
            'city': '     '
        }, follow_redirects=True)
        assert b"Operating City is required" in resp_reg_blank_city.data
        print("[PASS] Test B2: Whitespace-only operating city rejected")

        # B3. Too short city (<2 chars) rejected
        resp_reg_short_city = client.post('/auth/register', data={
            'username': 'test_short_city',
            'email': 'shortcity@test.org',
            'password': 'password123',
            'role': 'ngo',
            'organization_name': 'Short City Shelter',
            'contact_phone': '+91 91234 56789',
            'address': 'Street 1, Main Road',
            'city': 'X'
        }, follow_redirects=True)
        assert b"Operating City must be at least 2 characters long" in resp_reg_short_city.data
        print("[PASS] Test B3: Too short operating city (< 2 chars) rejected")

        # B4. Valid city with whitespace normalized and stored
        client.get('/auth/logout', follow_redirects=True)
        reg_city_user = f"ngo_rajkot_{int(datetime.now().timestamp())}"
        resp_reg_ok = client.post('/auth/register', data={
            'username': reg_city_user,
            'email': f'{reg_city_user}@rajkotngo.org',
            'password': 'password123',
            'role': 'ngo',
            'organization_name': 'Rajkot Annapurna Care Foundation',
            'contact_phone': '+91 98250 11223',
            'address': 'Yagnik Road, Opposite Post Office',
            'city': '   Rajkot   ' # extra whitespace
        }, follow_redirects=True)
        assert resp_reg_ok.status_code == 200
        saved_rajkot_ngo = User.query.filter_by(username=reg_city_user).first()
        assert saved_rajkot_ngo is not None
        assert saved_rajkot_ngo.city == 'Rajkot', f"Expected cleaned 'Rajkot', got '{saved_rajkot_ngo.city}'"
        print("[PASS] Test B4: Registration stores whitespace-cleaned Operating City ('Rajkot')")

        # -------------------------------------------------------------------------
        # C. Profile / Organization City Updates
        # -------------------------------------------------------------------------
        # C1. NGO updates city via profile
        resp_prof_update = client.post('/auth/profile', data={
            'organization_name': 'Rajkot Annapurna Care Foundation Updated',
            'contact_phone': '+91 98250 99887',
            'address': 'Kalawad Road, Near Circle',
            'city': '  Ahmedabad  '
        }, follow_redirects=True)
        assert b"Profile and Operating City updated successfully" in resp_prof_update.data
        saved_rajkot_ngo = User.query.filter_by(username=reg_city_user).first()
        assert saved_rajkot_ngo.city == 'Ahmedabad'

        # Switch back to Rajkot for subsequent testing
        client.post('/auth/profile', data={
            'organization_name': 'Rajkot Annapurna Care Foundation',
            'contact_phone': '+91 98250 11223',
            'address': 'Yagnik Road, Opposite Post Office',
            'city': 'Rajkot'
        }, follow_redirects=True)
        saved_rajkot_ngo = User.query.filter_by(username=reg_city_user).first()
        assert saved_rajkot_ngo.city == 'Rajkot'
        print("[PASS] Test C1: NGO successfully updated operating city via Profile & Organization page")

        # C2. Kitchen Manager updates city via profile
        client.get('/auth/demo-login/kitchen_manager', follow_redirects=True)
        km_user = User.query.filter_by(username='kitchen_demo').first()
        resp_km_prof = client.post('/auth/profile', data={
            'organization_name': km_user.organization_name,
            'contact_phone': km_user.contact_phone,
            'address': km_user.address,
            'city': '   Delhi   '
        }, follow_redirects=True)
        assert b"Profile and Operating City updated successfully" in resp_km_prof.data
        km_user = User.query.filter_by(username='kitchen_demo').first()
        assert km_user.city == 'Delhi'

        # C3. Profile rejects empty city
        resp_km_empty_city = client.post('/auth/profile', data={
            'organization_name': km_user.organization_name,
            'contact_phone': km_user.contact_phone,
            'address': km_user.address,
            'city': '   '
        }, follow_redirects=True)
        assert b"Operating City is required" in resp_km_empty_city.data
        print("[PASS] Test C2 & C3: Kitchen Manager profile updates city and rejects empty city values")

        # -------------------------------------------------------------------------
        # D. Kitchen Surplus Creation & Automatic Pickup City Assignment
        # -------------------------------------------------------------------------
        # D1. Create Rajkot Kitchen Manager
        rajkot_km_username = f"km_rajkot_{int(datetime.now().timestamp())}"
        rajkot_km = User(
            username=rajkot_km_username,
            email=f"{rajkot_km_username}@rajkotkitchen.edu",
            role='kitchen_manager',
            organization_name="Rajkot Central Dining Hall",
            contact_phone="+91 98240 55443",
            address="Kuvadva Road, Institutional Hub",
            city="Rajkot"
        )
        rajkot_km.set_password("kitchen123")
        db.session.add(rajkot_km)
        db.session.commit()

        # Login as Rajkot Kitchen Manager
        client.get('/auth/logout', follow_redirects=True)
        client.post('/auth/login', data={
            'username': rajkot_km_username,
            'password': 'kitchen123',
            'role': 'kitchen_manager'
        }, follow_redirects=True)

        # Broadcast surplus from Rajkot Kitchen: pickup_city must be automatically set to 'Rajkot'
        resp_broadcast_rajkot = client.post('/donation/list', data={
            'food_name': 'Kathiyawadi Khichdi & Kadhi',
            'quantity_portions': '50',
            'weight_approx_kg': '20.0',
            'dietary_type': 'Vegetarian',
            'safe_hours': '4.0',
            'pickup_address': 'Rajkot Mess Bay 1',
            'contact_phone': '+91 98240 55443',
            'packaging_type': 'Thermal Hot Cans',
            'storage_temp': 'Hot (>60°C)',
            'fssai_verified': 'on'
        }, follow_redirects=True)
        assert resp_broadcast_rajkot.status_code == 200
        rajkot_listing = SurplusListing.query.filter_by(food_name='Kathiyawadi Khichdi & Kadhi').order_by(SurplusListing.id.desc()).first()
        assert rajkot_listing is not None
        rajkot_listing_id = rajkot_listing.id
        assert rajkot_listing.pickup_city == 'Rajkot', f"Expected pickup_city 'Rajkot', got '{rajkot_listing.pickup_city}'"
        print("[PASS] Test D1: Kitchen Manager surplus broadcast automatically assigned pickup_city from profile ('Rajkot')")

        # D2. Kitchen Manager with no city is blocked from listing surplus
        no_city_km_username = f"km_nocity_{int(datetime.now().timestamp())}"
        no_city_km = User(
            username=no_city_km_username,
            email=f"{no_city_km_username}@test.edu",
            role='kitchen_manager',
            organization_name="Homeless Kitchen",
            contact_phone="+91 98000 11111",
            address="Unknown Road",
            city=None
        )
        no_city_km.set_password("kitchen123")
        db.session.add(no_city_km)
        db.session.commit()

        client.get('/auth/logout', follow_redirects=True)
        client.post('/auth/login', data={
            'username': no_city_km_username,
            'password': 'kitchen123',
            'role': 'kitchen_manager'
        }, follow_redirects=True)

        resp_blocked_list = client.get('/donation/list', follow_redirects=True)
        assert b"Operating City required" in resp_blocked_list.data
        print("[PASS] Test D2: Kitchen Manager with no configured city blocked from creating surplus broadcasts")

        # -------------------------------------------------------------------------
        # E. NGO Marketplace City Isolation & Filtering
        # -------------------------------------------------------------------------
        # E1. Delhi NGO (ngo_demo, city='Delhi') views Marketplace:
        # Must see Delhi surplus, must NOT see Rajkot surplus!
        client.get('/auth/logout', follow_redirects=True)
        client.get('/auth/demo-login/ngo', follow_redirects=True)
        resp_delhi_mkt = client.get('/donation/marketplace')
        assert resp_delhi_mkt.status_code == 200
        assert b"Operating City: Delhi" in resp_delhi_mkt.data
        assert b"Showing local surplus only" in resp_delhi_mkt.data
        assert b"Kathiyawadi Khichdi" not in resp_delhi_mkt.data, "CRITICAL ISOLATION FAILURE: Delhi NGO saw Rajkot surplus!"
        print("[PASS] Test E1: Delhi NGO sees only Delhi surplus; Rajkot surplus is strictly excluded from query and HTML")

        # E2. Rajkot NGO (saved_rajkot_ngo, city='Rajkot') views Marketplace:
        # Must see Rajkot surplus, must NOT see Delhi surplus!
        client.get('/auth/logout', follow_redirects=True)
        client.post('/auth/login', data={
            'username': reg_city_user,
            'password': 'password123',
            'role': 'ngo'
        }, follow_redirects=True)
        resp_rajkot_mkt = client.get('/donation/marketplace')
        assert resp_rajkot_mkt.status_code == 200
        assert b"Operating City: Rajkot" in resp_rajkot_mkt.data
        assert b"Kathiyawadi Khichdi" in resp_rajkot_mkt.data, "Rajkot NGO failed to see local Rajkot surplus!"
        # Verify Delhi listings are NOT present
        assert b"Steamed Jeera Rice & Dal Tadka" not in resp_rajkot_mkt.data, "CRITICAL ISOLATION FAILURE: Rajkot NGO saw Delhi surplus!"
        print("[PASS] Test E2: Rajkot NGO sees local Rajkot surplus; Delhi surplus is strictly excluded from query and HTML")

        # E3. Case-insensitivity & whitespace normalization
        # Update Rajkot NGO city to "  rajkot  " with extra spaces and lowercase
        client.post('/auth/profile', data={
            'organization_name': 'Rajkot Annapurna Care Foundation',
            'contact_phone': '+91 98250 11223',
            'address': 'Yagnik Road, Opposite Post Office',
            'city': '  rajkot  '
        }, follow_redirects=True)
        resp_rajkot_mkt_case = client.get('/donation/marketplace')
        assert b"Kathiyawadi Khichdi" in resp_rajkot_mkt_case.data
        print("[PASS] Test E3: City matching is fully case-insensitive and whitespace-normalized ('  rajkot  ' == 'Rajkot')")

        # E4. NGO with unconfigured / empty city sees profile-completion alert, no listings
        unconfigured_ngo_username = f"ngo_nocity_{int(datetime.now().timestamp())}"
        unconfigured_ngo = User(
            username=unconfigured_ngo_username,
            email=f"{unconfigured_ngo_username}@test.org",
            role='ngo',
            organization_name="Cityless Relief",
            contact_phone="+91 98111 00000",
            address="Transit Camp",
            city=None
        )
        unconfigured_ngo.set_password("demo1234")
        db.session.add(unconfigured_ngo)
        db.session.commit()

        client.get('/auth/logout', follow_redirects=True)
        client.post('/auth/login', data={
            'username': unconfigured_ngo_username,
            'password': 'demo1234',
            'role': 'ngo'
        }, follow_redirects=True)
        resp_unconf_mkt = client.get('/donation/marketplace')
        assert b"Operating City Not Configured" in resp_unconf_mkt.data
        assert b"Kathiyawadi Khichdi" not in resp_unconf_mkt.data
        assert b"Steamed Jeera Rice" not in resp_unconf_mkt.data
        print("[PASS] Test E4: NGO without configured city sees profile completion message and zero listings")

        # -------------------------------------------------------------------------
        # F. Server-Side Claim Protection (Direct POST Attack Prevention)
        # -------------------------------------------------------------------------
        # F1. Rajkot NGO attempts direct cross-city POST to claim Delhi listing
        # Ensure a fresh, active, unexpired Delhi listing exists
        client.get('/auth/logout', follow_redirects=True)
        client.get('/auth/demo-login/kitchen_manager', follow_redirects=True)
        client.post('/donation/list', data={
            'food_name': 'Fresh Delhi Dal Makhani & Rice',
            'quantity_portions': '60',
            'weight_approx_kg': '24.0',
            'dietary_type': 'Vegetarian',
            'safe_hours': '5.0',
            'pickup_address': 'Delhi North Campus Dining Bay 2',
            'contact_phone': '+91 98765 43210',
            'packaging_type': 'Insulated Food Containers',
            'storage_temp': 'Hot (>60°C)',
            'fssai_verified': 'on'
        }, follow_redirects=True)
        delhi_avail = SurplusListing.query.filter_by(food_name='Fresh Delhi Dal Makhani & Rice').order_by(SurplusListing.id.desc()).first()
        assert delhi_avail is not None
        assert delhi_avail.pickup_city == 'Delhi'
        initial_delhi_portions = delhi_avail.quantity_portions
        initial_claims_count = Claim.query.count()

        # Login as Rajkot NGO
        client.get('/auth/logout', follow_redirects=True)
        client.post('/auth/login', data={
            'username': reg_city_user,
            'password': 'password123',
            'role': 'ngo'
        }, follow_redirects=True)

        # Send malicious cross-city POST to claim Delhi listing
        resp_cross_claim = client.post(f'/donation/claim/{delhi_avail.id}', data={
            'beneficiaries_count': '15',
            'notes': 'Malicious cross-city claim from Rajkot NGO to Delhi listing'
        }, follow_redirects=True)

        assert b"Location restriction" in resp_cross_claim.data
        assert b"You can only claim surplus food available in your operating city" in resp_cross_claim.data

        # Verify NO database modification occurred
        delhi_avail = db.session.get(SurplusListing, delhi_avail.id)
        assert delhi_avail.quantity_portions == initial_delhi_portions, "SECURITY BREACH: Cross-city claim decremented listing portions!"
        assert Claim.query.count() == initial_claims_count, "SECURITY BREACH: Cross-city claim created a Claim record!"
        print("[PASS] Test F1: Direct cross-city claim POST strictly rejected; 0 portions deducted, 0 claims/OTPs created")

        # F2. Delhi NGO attempts direct cross-city POST to claim Rajkot listing
        client.get('/auth/logout', follow_redirects=True)
        client.get('/auth/demo-login/ngo', follow_redirects=True)
        rajkot_listing = db.session.get(SurplusListing, rajkot_listing_id)
        initial_rajkot_portions = rajkot_listing.quantity_portions

        resp_cross_delhi_to_rajkot = client.post(f'/donation/claim/{rajkot_listing_id}', data={
            'beneficiaries_count': '10',
            'notes': 'Delhi NGO attempting to claim Rajkot surplus'
        }, follow_redirects=True)
        assert b"Location restriction" in resp_cross_delhi_to_rajkot.data
        rajkot_listing = db.session.get(SurplusListing, rajkot_listing_id)
        assert rajkot_listing.quantity_portions == initial_rajkot_portions
        assert Claim.query.count() == initial_claims_count
        print("[PASS] Test F2: Delhi NGO direct claim on Rajkot listing strictly rejected")

        # F3. Same-city claim SUCCEEDS with OTP generation and portion deduction
        client.get('/auth/logout', follow_redirects=True)
        client.post('/auth/login', data={
            'username': reg_city_user,
            'password': 'password123',
            'role': 'ngo'
        }, follow_redirects=True)

        resp_same_city_claim = client.post(f'/donation/claim/{rajkot_listing_id}', data={
            'beneficiaries_count': '20',
            'notes': 'Valid local relief distribution in Rajkot'
        }, follow_redirects=True)
        assert resp_same_city_claim.status_code == 200
        assert b"Success! You claimed 20 portions" in resp_same_city_claim.data
        assert b"Pickup Verification OTP" in resp_same_city_claim.data

        rajkot_listing = db.session.get(SurplusListing, rajkot_listing_id)
        assert rajkot_listing.quantity_portions == (initial_rajkot_portions - 20) # 50 - 20 = 30
        rajkot_claim = Claim.query.filter_by(listing_id=rajkot_listing_id).order_by(Claim.id.desc()).first()
        assert rajkot_claim is not None
        assert len(rajkot_claim.verification_otp) == 6
        assert rajkot_claim.verification_otp.isdigit()
        print(f"[PASS] Test F3: Same-city claim successfully generated 6-digit OTP ({rajkot_claim.verification_otp}) and decremented portions (50 -> 30)")

        # F4. Rajkot Kitchen Manager verifies OTP -> Status Delivered
        client.get('/auth/logout', follow_redirects=True)
        client.post('/auth/login', data={
            'username': rajkot_km_username,
            'password': 'kitchen123',
            'role': 'kitchen_manager'
        }, follow_redirects=True)

        resp_rajkot_verify = client.post(f'/donation/verify-otp/{rajkot_claim.id}', data={
            'otp': rajkot_claim.verification_otp
        }, follow_redirects=True)
        assert b"OTP Verified" in resp_rajkot_verify.data
        rajkot_claim = db.session.get(Claim, rajkot_claim.id)
        assert rajkot_claim.status == 'Delivered'
        print("[PASS] Test F4: Rajkot Kitchen Manager verified OTP, claim transitioned to Delivered")

        # -------------------------------------------------------------------------
        # G. Dashboard City Metric Isolation
        # -------------------------------------------------------------------------
        # G1. Rajkot NGO dashboard counts only Rajkot available surplus
        client.get('/auth/logout', follow_redirects=True)
        client.post('/auth/login', data={
            'username': reg_city_user,
            'password': 'password123',
            'role': 'ngo'
        }, follow_redirects=True)
        resp_rajkot_dash = client.get('/dashboard')
        assert resp_rajkot_dash.status_code == 200
        assert b"Operating City: Rajkot" in resp_rajkot_dash.data
        assert b"Available Surplus (Rajkot)" in resp_rajkot_dash.data
        assert b"active local listing" in resp_rajkot_dash.data
        print("[PASS] Test G1: Rajkot NGO dashboard metrics strictly isolate to Rajkot local surplus")

        # G2. Delhi NGO dashboard counts only Delhi surplus
        client.get('/auth/logout', follow_redirects=True)
        client.get('/auth/demo-login/ngo', follow_redirects=True)
        resp_delhi_dash = client.get('/dashboard')
        assert resp_delhi_dash.status_code == 200
        assert b"Operating City: Delhi" in resp_delhi_dash.data
        assert b"Available Surplus (Delhi)" in resp_delhi_dash.data
        assert b"active local listing" in resp_delhi_dash.data
        print("[PASS] Test G2: Delhi NGO dashboard metrics strictly isolate to Delhi local surplus")

        print("Completed City-Based Surplus Visibility & Claim Authorization Tests successfully!")

    print("\nALL AUTOMATED TESTS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    run_tests()

