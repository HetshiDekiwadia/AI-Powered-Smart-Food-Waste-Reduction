from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(32), nullable=False, default='kitchen_manager') # 'kitchen_manager', 'ngo', 'admin'
    organization_name = db.Column(db.String(120), nullable=False)
    contact_phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    waste_logs = db.relationship('WasteLog', backref='logger', lazy=True)
    surplus_listings = db.relationship('SurplusListing', backref='donor', lazy=True)
    claims = db.relationship('Claim', backref='claimant_ngo', lazy=True)
    food_preparation_plans = db.relationship('FoodPreparationPlan', backref='planner', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'

class WasteLog(db.Model):
    __tablename__ = 'waste_logs'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=lambda: datetime.now(timezone.utc).date())
    meal_session = db.Column(db.String(32), nullable=False) # Breakfast, Lunch, Snacks, Dinner
    waste_category = db.Column(db.String(32), nullable=False) # Prep Waste, Plate Waste, Spoilage, Buffet Leftover
    food_item = db.Column(db.String(100), nullable=False)
    weight_kg = db.Column(db.Float, nullable=False)
    reason = db.Column(db.String(255), nullable=True)
    estimated_cost_loss = db.Column(db.Float, nullable=False, default=0.0) # In INR
    logged_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<WasteLog {self.food_item} - {self.weight_kg}kg>'

class InventoryItem(db.Model):
    __tablename__ = 'inventory_items'

    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False) # Grains, Vegetables, Dairy, Bakery, Spices
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=False, default='kg') # kg, Liters, Packets
    expiry_date = db.Column(db.Date, nullable=False)
    min_threshold = db.Column(db.Float, nullable=False, default=5.0)
    cost_per_unit = db.Column(db.Float, nullable=False, default=50.0)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    @property
    def days_until_expiry(self):
        today = datetime.now(timezone.utc).date()
        return (self.expiry_date - today).days

    @property
    def status_alert(self):
        days = self.days_until_expiry
        if days < 0:
            return 'Expired'
        elif days <= 2:
            return 'Critical'
        elif days <= 5:
            return 'Near Expiry'
        return 'Optimal'

class SurplusListing(db.Model):
    __tablename__ = 'surplus_listings'

    id = db.Column(db.Integer, primary_key=True)
    food_name = db.Column(db.String(120), nullable=False)
    quantity_portions = db.Column(db.Integer, nullable=False)
    weight_approx_kg = db.Column(db.Float, nullable=False)
    dietary_type = db.Column(db.String(32), nullable=False) # Vegetarian, Non-Vegetarian, Vegan
    prepared_time = db.Column(db.DateTime, nullable=False)
    safe_until = db.Column(db.DateTime, nullable=False)
    packaging_type = db.Column(db.String(50), nullable=False, default='Food-Grade Steel Containers')
    storage_temp = db.Column(db.String(32), nullable=False, default='Hot (>60°C)')
    pickup_address = db.Column(db.String(255), nullable=False)
    pickup_city = db.Column(db.String(64), nullable=True)
    contact_phone = db.Column(db.String(20), nullable=False)
    fssai_verified = db.Column(db.Boolean, default=True)
    status = db.Column(db.String(32), default='Available') # Available, Claimed, Dispatched, Completed, Cancelled
    donor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    claims = db.relationship('Claim', backref='listing', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<SurplusListing {self.food_name} ({self.quantity_portions} portions)>'

class Claim(db.Model):
    __tablename__ = 'claims'

    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('surplus_listings.id'), nullable=False)
    ngo_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    beneficiaries_count = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(32), default='Claimed') # Claimed, Picked Up, Delivered
    verification_otp = db.Column(db.String(6), nullable=False)
    notes = db.Column(db.String(255), nullable=True)
    claimed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    delivered_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<Claim #{self.id} for Listing {self.listing_id}>'

class FoodPreparationPlan(db.Model):
    __tablename__ = 'food_preparation_plans'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    predicted_attendance = db.Column(db.Integer, nullable=False)
    safety_buffer = db.Column(db.Float, nullable=False)
    meal_session = db.Column(db.String(32), nullable=False, default='Lunch')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    items = db.relationship('FoodPreparationItem', backref='plan', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<FoodPreparationPlan #{self.id} for {self.predicted_attendance} diners (Buffer: {self.safety_buffer}%)>'

class FoodPreparationItem(db.Model):
    __tablename__ = 'food_preparation_items'

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('food_preparation_plans.id'), nullable=False)
    food_name = db.Column(db.String(120), nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    quantity_per_person = db.Column(db.Float, nullable=False)
    recommended_quantity = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def estimated_quantity(self):
        return self.recommended_quantity

    @property
    def estimated_unit(self):
        return self.unit

    @property
    def serving_benchmark(self):
        return self.quantity_per_person

    def __repr__(self):
        return f'<FoodPreparationItem {self.food_name}: {self.recommended_quantity} {self.unit}>'
