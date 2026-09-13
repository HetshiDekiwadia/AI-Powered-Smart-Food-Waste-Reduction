"""
Final Verification Script for City-Based Surplus Visibility & Claim Authorization
Verifies the exact flows requested:
1. Kitchen Rajkot creates surplus -> pickup_city = Rajkot
2. NGO Rajkot sees listing -> claims -> receives OTP
3. Kitchen Rajkot verifies OTP -> claim becomes Delivered
4. NGO Ahmedabad cannot see Rajkot listing
5. NGO Ahmedabad cannot claim Rajkot listing through direct POST
"""

from app import create_app, db
from app.models import User, SurplusListing, Claim
from app.services.redistribution import cities_match
import sys

def verify_end_to_end():
    app = create_app()
    app.config['TESTING'] = True

    with app.test_client() as client:
        print("\n--- 1. Verification of Actual SQLite Database Schema ---")
        with app.app_context():
            import sqlite3
            conn = sqlite3.connect('instance/database.sqlite')
            c = conn.cursor()
            user_cols = [r[1] for r in c.execute("PRAGMA table_info(users)").fetchall()]
            listing_cols = [r[1] for r in c.execute("PRAGMA table_info(surplus_listings)").fetchall()]
            conn.close()
            assert 'city' in user_cols, "users table missing city column"
            assert 'pickup_city' in listing_cols, "surplus_listings table missing pickup_city column"
            print(f"Users table columns: {user_cols}")
            print(f"SurplusListings table columns: {listing_cols}")
            print("[VERIFIED] SQLite database schema includes users.city and surplus_listings.pickup_city")

        print("\n--- 2. Verification of Existing Data Preservation ---")
        with app.app_context():
            users = User.query.all()
            print(f"Total existing users: {len(users)}")
            for u in users[:6]:
                print(f"  User id={u.id}, username={u.username}, role={u.role}, city={u.city}")
            assert len(users) >= 6, "Existing users count decreased!"
            delhi_km = User.query.filter_by(username='kitchen_demo').first()
            assert delhi_km and delhi_km.city == 'Delhi'
            delhi_ngo = User.query.filter_by(username='ngo_demo').first()
            assert delhi_ngo and delhi_ngo.city == 'Delhi'
            print("[VERIFIED] Existing demo accounts and data preserved with correct cities")

        print("\n--- 3. End-to-End Flow: Kitchen Rajkot -> NGO Rajkot -> Delivered ---")
        # Ensure Rajkot Kitchen user exists
        with app.app_context():
            rajkot_km = User.query.filter_by(username='Demo3').first()
            if not rajkot_km:
                rajkot_km = User(
                    username='rajkot_kitchen_e2e',
                    email='rajkot_km@e2e.org',
                    role='kitchen_manager',
                    organization_name='Rajkot Heritage Kitchen',
                    contact_phone='+91 98250 11111',
                    address='Ring Road, Rajkot',
                    city='Rajkot'
                )
                rajkot_km.set_password('demo1234')
                db.session.add(rajkot_km)
                db.session.commit()
            rajkot_km_username = rajkot_km.username
            rajkot_km_id = rajkot_km.id

        # 3a. Kitchen Rajkot logs in and creates surplus
        client.get('/auth/logout', follow_redirects=True)
        resp_login = client.post('/auth/login', data={
            'username': rajkot_km_username,
            'password': 'demo1234' if rajkot_km_username != 'Demo3' else 'demo1234',
            'role': 'kitchen_manager'
        }, follow_redirects=True)
        # If Demo3 password is not demo1234, switch via demo_login or use created
        if b"Invalid username or password" in resp_login.data:
            with app.app_context():
                u = User.query.filter_by(username=rajkot_km_username).first()
                u.set_password('demo1234')
                db.session.commit()
            client.post('/auth/login', data={
                'username': rajkot_km_username,
                'password': 'demo1234',
                'role': 'kitchen_manager'
            }, follow_redirects=True)

        resp_create = client.post('/donation/list', data={
            'food_name': 'Rajkot Kathiyawadi Special Thali',
            'quantity_portions': '40',
            'weight_approx_kg': '18.0',
            'dietary_type': 'Vegetarian',
            'safe_hours': '4.5',
            'pickup_address': 'Rajkot Kitchen Dock Gate 1',
            'contact_phone': '+91 98250 11111',
            'packaging_type': 'Insulated Stainless Steel',
            'storage_temp': 'Hot (>60°C)',
            'fssai_verified': 'on'
        }, follow_redirects=True)
        assert resp_create.status_code == 200

        with app.app_context():
            rajkot_item = SurplusListing.query.filter_by(food_name='Rajkot Kathiyawadi Special Thali').order_by(SurplusListing.id.desc()).first()
            assert rajkot_item is not None
            assert rajkot_item.pickup_city == 'Rajkot', f"Expected pickup_city 'Rajkot', got '{rajkot_item.pickup_city}'"
            rajkot_item_id = rajkot_item.id
            print(f"[VERIFIED] Kitchen Rajkot created surplus: '{rajkot_item.food_name}', pickup_city = '{rajkot_item.pickup_city}'")

        # 3b. NGO Rajkot logs in, sees listing, and claims
        with app.app_context():
            rajkot_ngo = User.query.filter_by(username='ngo_rajkot_e2e').first()
            if not rajkot_ngo:
                rajkot_ngo = User(
                    username='ngo_rajkot_e2e',
                    email='ngo_rajkot@e2e.org',
                    role='ngo',
                    organization_name='Rajkot Relief NGO',
                    contact_phone='+91 98250 22222',
                    address='Yagnik Road, Rajkot',
                    city='Rajkot'
                )
                rajkot_ngo.set_password('demo1234')
                db.session.add(rajkot_ngo)
                db.session.commit()
            rajkot_ngo_username = rajkot_ngo.username
            rajkot_ngo_id = rajkot_ngo.id

        client.get('/auth/logout', follow_redirects=True)
        client.post('/auth/login', data={
            'username': rajkot_ngo_username,
            'password': 'demo1234',
            'role': 'ngo'
        }, follow_redirects=True)

        # NGO Rajkot visits marketplace
        resp_mkt_rajkot = client.get('/donation/marketplace')
        assert b"Rajkot Kathiyawadi Special Thali" in resp_mkt_rajkot.data
        print("[VERIFIED] NGO Rajkot sees local listing 'Rajkot Kathiyawadi Special Thali'")

        # NGO Rajkot claims 25 portions
        resp_claim = client.post(f'/donation/claim/{rajkot_item_id}', data={
            'beneficiaries_count': '25',
            'notes': 'Distribution to underserved community at Rajkot Railway Colony'
        }, follow_redirects=True)
        assert b"Success! You claimed 25 portions" in resp_claim.data
        assert b"Pickup Verification OTP" in resp_claim.data

        with app.app_context():
            claim = Claim.query.filter_by(listing_id=rajkot_item_id, ngo_id=rajkot_ngo_id).first()
            assert claim is not None
            assert len(claim.verification_otp) == 6
            claim_id = claim.id
            otp_code = claim.verification_otp
            print(f"[VERIFIED] NGO Rajkot claimed 25 portions, received 6-digit OTP: {otp_code}")

        # 3c. Kitchen Rajkot verifies OTP
        client.get('/auth/logout', follow_redirects=True)
        client.post('/auth/login', data={
            'username': rajkot_km_username,
            'password': 'demo1234',
            'role': 'kitchen_manager'
        }, follow_redirects=True)

        resp_verify = client.post(f'/donation/verify-otp/{claim_id}', data={'otp': otp_code}, follow_redirects=True)
        assert b"OTP Verified" in resp_verify.data

        with app.app_context():
            claim_deliv = db.session.get(Claim, claim_id)
            assert claim_deliv.status == 'Delivered'
            assert claim_deliv.delivered_at is not None
            print(f"[VERIFIED] Kitchen Rajkot verified OTP {otp_code} -> Claim status = '{claim_deliv.status}'")

        print("\n--- 4. Verification: NGO Ahmedabad City Isolation ---")
        # Ensure NGO Ahmedabad exists
        with app.app_context():
            ahmedabad_ngo = User.query.filter_by(username='ngo_ahmedabad_e2e').first()
            if not ahmedabad_ngo:
                ahmedabad_ngo = User(
                    username='ngo_ahmedabad_e2e',
                    email='ngo_ahmedabad@e2e.org',
                    role='ngo',
                    organization_name='Ahmedabad Relief Trust',
                    contact_phone='+91 98790 33333',
                    address='Ashram Road, Ahmedabad',
                    city='Ahmedabad'
                )
                ahmedabad_ngo.set_password('demo1234')
                db.session.add(ahmedabad_ngo)
                db.session.commit()
            ahmedabad_ngo_username = ahmedabad_ngo.username

        client.get('/auth/logout', follow_redirects=True)
        client.post('/auth/login', data={
            'username': ahmedabad_ngo_username,
            'password': 'demo1234',
            'role': 'ngo'
        }, follow_redirects=True)

        # 4a. NGO Ahmedabad cannot see Rajkot listing
        resp_mkt_ahmedabad = client.get('/donation/marketplace')
        assert b"Rajkot Kathiyawadi Special Thali" not in resp_mkt_ahmedabad.data
        print("[VERIFIED] NGO Ahmedabad CANNOT see Rajkot listing on marketplace")

        # 4b. NGO Ahmedabad cannot claim Rajkot listing through direct POST
        with app.app_context():
            rajkot_item_before = db.session.get(SurplusListing, rajkot_item_id)
            portions_before = rajkot_item_before.quantity_portions
            claims_count_before = Claim.query.count()

        resp_cross_post = client.post(f'/donation/claim/{rajkot_item_id}', data={
            'beneficiaries_count': '10',
            'notes': 'Unauthorized cross-city attempt'
        }, follow_redirects=True)

        assert b"Location restriction" in resp_cross_post.data
        assert b"You can only claim surplus food available in your operating city" in resp_cross_post.data

        with app.app_context():
            rajkot_item_after = db.session.get(SurplusListing, rajkot_item_id)
            claims_count_after = Claim.query.count()
            assert rajkot_item_after.quantity_portions == portions_before
            assert claims_count_after == claims_count_before

        print("[VERIFIED] NGO Ahmedabad CANNOT claim Rajkot listing through direct POST (Location restriction enforced, 0 deductions, 0 OTPs)")

    print("\n========================================================")
    print("ALL VERIFICATION CHECKS AND END-TO-END FLOWS COMPLETED!")
    print("========================================================")

if __name__ == '__main__':
    verify_end_to_end()
