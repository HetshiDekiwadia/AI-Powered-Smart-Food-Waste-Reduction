"""
Seed database with realistic institutional kitchen data for SIH evaluation.
Run with: python seed_data.py
"""

from datetime import datetime, timezone, timedelta, date
from app import create_app, db
from app.models import User, WasteLog, InventoryItem, SurplusListing, Claim

app = create_app()

def seed():
    with app.app_context():
        # Clear existing tables
        db.drop_all()
        db.create_all()

        print("Creating default personas...")
        # 1. Kitchen Manager
        kitchen_user = User(
            username='kitchen_demo',
            email='kitchen@apex.edu',
            role='kitchen_manager',
            organization_name='Apex University Central Mega-Mess',
            contact_phone='+91 98765 43210',
            address='Campus Block B, Dining Complex, North Campus'
        )
        kitchen_user.set_password('demo1234')
        db.session.add(kitchen_user)

        # 2. NGO Partner
        ngo_user = User(
            username='ngo_demo',
            email='coordinator@annapurnarescue.org',
            role='ngo',
            organization_name='Annapurna Food Rescue Foundation',
            contact_phone='+91 98111 22334',
            address='Unit 12, Community Relief Center, Civil Lines'
        )
        ngo_user.set_password('demo1234')
        db.session.add(ngo_user)

        db.session.commit()

        print("Seeding smart kitchen inventory...")
        today = datetime.now(timezone.utc).date()
        inventory_data = [
            ("Basmati Rice Grade-A", "Grains", 350.0, "kg", today + timedelta(days=45), 25.0, 52.0),
            ("Fresh Farm Tomatoes", "Vegetables", 14.5, "kg", today + timedelta(days=1), 5.0, 28.0), # Near Expiry!
            ("Full Cream Milk (5L pouches)", "Dairy", 25.0, "Liters", today + timedelta(days=2), 10.0, 64.0), # Critical!
            ("Whole Wheat Atta", "Grains", 280.0, "kg", today + timedelta(days=60), 30.0, 38.0),
            ("Fresh Cottage Cheese (Paneer)", "Dairy", 8.0, "kg", today + timedelta(days=2), 4.0, 320.0), # Near Expiry!
            ("Refined Sunflower Oil", "Grains", 75.0, "Liters", today + timedelta(days=90), 15.0, 115.0),
            ("Potatoes & Onions", "Vegetables", 120.0, "kg", today + timedelta(days=12), 20.0, 22.0),
            ("Assorted Whole Spices", "Spices", 18.0, "kg", today + timedelta(days=180), 3.0, 240.0)
        ]

        for name, cat, qty, unit, exp, thresh, cost in inventory_data:
            item = InventoryItem(
                item_name=name,
                category=cat,
                quantity=qty,
                unit=unit,
                expiry_date=exp,
                min_threshold=thresh,
                cost_per_unit=cost
            )
            db.session.add(item)

        print("Seeding past food waste logs...")
        waste_samples = [
            (today - timedelta(days=4), "Breakfast", "Prep Waste", "Vegetable Peels & Trimmings", 6.2, "Standard peeling discard", 186.0),
            (today - timedelta(days=4), "Lunch", "Plate Waste", "Leftover Rice & Sambhar", 14.5, "Over-serving portions on plate", 870.0),
            (today - timedelta(days=3), "Lunch", "Buffet Leftover", "Cooked Mixed Veg Sabzi", 8.0, "Turnout 12% lower than expected", 520.0),
            (today - timedelta(days=3), "Dinner", "Plate Waste", "Chapati & Dal Leftover", 11.3, "Late night student turnout drop", 678.0),
            (today - timedelta(days=2), "Breakfast", "Spoilage", "Sour Milk Batch (3 pouches)", 6.0, "Chiller door left unsealed overnight", 384.0),
            (today - timedelta(days=2), "Dinner", "Plate Waste", "Fried Rice & Manchurian", 13.8, "Students reported recipe over-salted", 897.0),
            (today - timedelta(days=1), "Lunch", "Prep Waste", "Spinach stalks & damaged leaves", 4.5, "Bulk vendor sorting", 135.0),
            (today - timedelta(days=1), "Dinner", "Buffet Leftover", "Surplus Rajma Masala", 7.2, "Rainy weather reduced day-scholar count", 468.0),
            (today, "Lunch", "Plate Waste", "Plate Scraps & Rotis", 9.4, "Large single servings", 564.0),
        ]

        for w_date, session, cat, food, kg, reason, cost in waste_samples:
            log = WasteLog(
                date=w_date,
                meal_session=session,
                waste_category=cat,
                food_item=food,
                weight_kg=kg,
                reason=reason,
                estimated_cost_loss=cost,
                logged_by_id=kitchen_user.id
            )
            db.session.add(log)

        print("Seeding surplus food listings and completed redemptions...")
        now = datetime.now(timezone.utc)
        
        # 1. Available listing
        listing_avail = SurplusListing(
            food_name="Steamed Jeera Rice & Dal Tadka",
            quantity_portions=55,
            weight_approx_kg=22.0,
            dietary_type="Vegetarian",
            prepared_time=now - timedelta(hours=1),
            safe_until=now + timedelta(hours=3, minutes=30),
            packaging_type="Insulated Food-Grade Containers",
            storage_temp="Hot (>65°C)",
            pickup_address="Apex Mega-Mess, Gate 2 Kitchen Bay",
            contact_phone="+91 98765 43210",
            fssai_verified=True,
            status='Available',
            donor_id=kitchen_user.id
        )
        db.session.add(listing_avail)

        # 2. Another available listing
        listing_avail2 = SurplusListing(
            food_name="Fresh Vegetable Khichdi & Pickle",
            quantity_portions=35,
            weight_approx_kg=14.0,
            dietary_type="Vegetarian",
            prepared_time=now - timedelta(minutes=45),
            safe_until=now + timedelta(hours=4),
            packaging_type="Sealed Thermal Dispensers",
            storage_temp="Hot (>60°C)",
            pickup_address="Apex Mega-Mess, Gate 2 Kitchen Bay",
            contact_phone="+91 98765 43210",
            fssai_verified=True,
            status='Available',
            donor_id=kitchen_user.id
        )
        db.session.add(listing_avail2)

        # 3. Completed claim (impact tracked)
        listing_completed = SurplusListing(
            food_name="Paneer Butter Masala & 120 Phulkas",
            quantity_portions=60,
            weight_approx_kg=24.0,
            dietary_type="Vegetarian",
            prepared_time=now - timedelta(days=1, hours=2),
            safe_until=now - timedelta(days=1),
            packaging_type="Food Grade Foil Containers",
            storage_temp="Hot (>60°C)",
            pickup_address="Apex Mega-Mess, Gate 2 Kitchen Bay",
            contact_phone="+91 98765 43210",
            fssai_verified=True,
            status='Completed',
            donor_id=kitchen_user.id
        )
        db.session.add(listing_completed)
        db.session.commit()

        claim_completed = Claim(
            listing_id=listing_completed.id,
            ngo_id=ngo_user.id,
            beneficiaries_count=60,
            status='Delivered',
            verification_otp='492815',
            notes='Distributed at Sector 14 Night Shelter for underprivileged youth.',
            claimed_at=now - timedelta(days=1, hours=1, minutes=30),
            delivered_at=now - timedelta(days=1, minutes=45)
        )
        db.session.add(claim_completed)

        # 4. Another completed claim
        listing_completed2 = SurplusListing(
            food_name="Vegetable Biryani with Raita",
            quantity_portions=80,
            weight_approx_kg=32.0,
            dietary_type="Vegetarian",
            prepared_time=now - timedelta(days=2, hours=3),
            safe_until=now - timedelta(days=2),
            packaging_type="Insulated Food-Grade Containers",
            storage_temp="Hot (>60°C)",
            pickup_address="Apex Mega-Mess, Gate 2 Kitchen Bay",
            contact_phone="+91 98765 43210",
            fssai_verified=True,
            status='Completed',
            donor_id=kitchen_user.id
        )
        db.session.add(listing_completed2)
        db.session.commit()

        claim_completed2 = Claim(
            listing_id=listing_completed2.id,
            ngo_id=ngo_user.id,
            beneficiaries_count=80,
            status='Delivered',
            verification_otp='813920',
            notes='Distributed at Railway Colony community kitchen.',
            claimed_at=now - timedelta(days=2, hours=2),
            delivered_at=now - timedelta(days=2, hours=1)
        )
        db.session.add(claim_completed2)

        db.session.commit()
        print("Database seeded successfully with realistic SIH demo data!")

if __name__ == '__main__':
    seed()
