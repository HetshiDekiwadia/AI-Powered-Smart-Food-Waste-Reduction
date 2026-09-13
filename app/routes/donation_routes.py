from datetime import datetime, timezone, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import func
from app import db
from app.models import SurplusListing, Claim
from app.services.redistribution import (
    generate_verification_otp,
    calculate_listing_urgency,
    normalize_city,
    cities_match
)
from app.decorators import kitchen_manager_required, ngo_required

donation_bp = Blueprint('donation', __name__)

@donation_bp.route('/list', methods=['GET', 'POST'])
@login_required
@kitchen_manager_required
def list_surplus():
    # Kitchen Manager must have an Operating City configured in their profile
    if not current_user.city or not current_user.city.strip():
        flash("Operating City required: Please complete your Operating City in Profile & Organization before broadcasting surplus food.", "warning")
        return redirect(url_for('auth.profile'))

    form_data = {
        'food_name': '',
        'quantity_portions': '',
        'weight_approx_kg': '',
        'dietary_type': 'Vegetarian',
        'packaging_type': 'Insulated Food-Grade Containers',
        'storage_temp': 'Hot (>60°C)',
        'safe_hours': '5.0',
        'contact_phone': current_user.contact_phone or '+91 98765 43210',
        'pickup_address': current_user.address or 'Campus Kitchen Loading Bay, Gate 3'
    }

    if request.method == 'POST':
        food_name = request.form.get('food_name', '').strip()
        dietary_type = request.form.get('dietary_type', 'Vegetarian').strip()
        packaging_type = request.form.get('packaging_type', 'Insulated Food-Grade Containers').strip()
        storage_temp = request.form.get('storage_temp', 'Hot (>60°C)').strip()
        safe_hours_raw = request.form.get('safe_hours', '5.0').strip()
        pickup_address = request.form.get('pickup_address', '').strip()
        contact_phone = request.form.get('contact_phone', '').strip()
        fssai_verified = request.form.get('fssai_verified') == 'on' or bool(request.form.get('fssai_verified'))

        quantity_raw = request.form.get('quantity_portions', '').strip()
        weight_raw = request.form.get('weight_approx_kg', '').strip()

        form_data.update({
            'food_name': food_name,
            'quantity_portions': quantity_raw,
            'weight_approx_kg': weight_raw,
            'dietary_type': dietary_type,
            'packaging_type': packaging_type,
            'storage_temp': storage_temp,
            'safe_hours': safe_hours_raw,
            'contact_phone': contact_phone,
            'pickup_address': pickup_address
        })

        # Server-side validation
        if not food_name:
            flash("Please enter the food name or description.", "warning")
            return render_template('redistribution/list_surplus.html', form_data=form_data)

        # Mandatory Food Safety Rule
        if not fssai_verified:
            flash("Food safety confirmation is mandatory. Only safe, hygienic surplus food may be broadcast for redistribution.", "danger")
            return render_template('redistribution/list_surplus.html', form_data=form_data)

        try:
            quantity_portions = int(quantity_raw)
            if quantity_portions <= 0:
                flash("Available portions must be a positive number greater than 0.", "warning")
                return render_template('redistribution/list_surplus.html', form_data=form_data)
            if quantity_portions > 10000:
                flash("Portions exceed realistic institutional batch limit (10,000).", "warning")
                return render_template('redistribution/list_surplus.html', form_data=form_data)
        except (ValueError, TypeError):
            flash("Please enter a valid whole number for available portions.", "warning")
            return render_template('redistribution/list_surplus.html', form_data=form_data)

        try:
            weight_approx_kg = float(weight_raw)
            if weight_approx_kg <= 0:
                flash("Approximate food weight must be greater than 0 kg.", "warning")
                return render_template('redistribution/list_surplus.html', form_data=form_data)
        except (ValueError, TypeError):
            flash("Please enter a valid numeric value for food weight in kg.", "warning")
            return render_template('redistribution/list_surplus.html', form_data=form_data)

        try:
            safe_hours = float(safe_hours_raw)
            if safe_hours <= 0 or safe_hours > 48:
                safe_hours = 4.0
        except (ValueError, TypeError):
            safe_hours = 4.0

        if not pickup_address:
            flash("Pickup address and location instructions are required.", "warning")
            return render_template('redistribution/list_surplus.html', form_data=form_data)

        if not contact_phone:
            flash("Dispatch contact phone number is required.", "warning")
            return render_template('redistribution/list_surplus.html', form_data=form_data)

        now = datetime.now(timezone.utc)
        safe_until = now + timedelta(hours=safe_hours)

        listing = SurplusListing(
            food_name=food_name,
            quantity_portions=quantity_portions,
            weight_approx_kg=round(weight_approx_kg, 1),
            dietary_type=dietary_type,
            prepared_time=now,
            safe_until=safe_until,
            packaging_type=packaging_type,
            storage_temp=storage_temp,
            pickup_address=pickup_address,
            pickup_city=current_user.city.strip(),
            contact_phone=contact_phone,
            fssai_verified=True,
            status='Available',
            donor_id=current_user.id
        )
        db.session.add(listing)
        db.session.commit()

        flash(f"Surplus broadcast created for '{food_name}' ({quantity_portions} portions). Nearby relief partners have been notified!", "success")
        return redirect(url_for('donation.marketplace'))

    return render_template('redistribution/list_surplus.html', form_data=form_data)

@donation_bp.route('/marketplace')
@login_required
def marketplace():
    now = datetime.now(timezone.utc)
    
    no_city_configured = False
    ngo_city = current_user.city.strip() if current_user.city else None

    if current_user.role == 'ngo':
        if not ngo_city:
            # NGO has no configured city: show clear profile-completion message, do not expose any listings
            listings = []
            no_city_configured = True
        else:
            norm_ngo_city = normalize_city(ngo_city)
            # Backend database query-level filtering: case-insensitive & whitespace-normalized
            db_candidates = SurplusListing.query.filter(
                SurplusListing.pickup_city.isnot(None),
                func.lower(func.trim(SurplusListing.pickup_city)) == norm_ngo_city
            ).order_by(SurplusListing.created_at.desc()).all()

            # Cross-verify with cities_match helper to guarantee exact normalization
            listings = [l for l in db_candidates if cities_match(l.pickup_city, ngo_city)]
    else:
        # Kitchen Manager or other roles
        listings = SurplusListing.query.order_by(SurplusListing.created_at.desc()).all()
    
    # Process urgency scores and safety eligibility for display
    cards = []
    for l in listings:
        urgency = calculate_listing_urgency(l.safe_until)
        safe_dt = l.safe_until.replace(tzinfo=timezone.utc) if l.safe_until.tzinfo is None else l.safe_until
        is_claimable = (
            l.status == 'Available' and 
            l.quantity_portions > 0 and 
            safe_dt > now and 
            l.fssai_verified
        )
        cards.append({
            'listing': l,
            'urgency': urgency,
            'is_claimable': is_claimable
        })

    return render_template(
        'redistribution/marketplace.html',
        cards=cards,
        no_city_configured=no_city_configured,
        user_city=ngo_city
    )

@donation_bp.route('/claim/<int:listing_id>', methods=['POST'])
@login_required
@ngo_required
def claim_listing(listing_id):
    # 1. Authenticated user (enforced by @login_required)
    # 2. Confirm role == NGO (enforced by @ngo_required)
    # 3. Confirm listing exists
    listing = SurplusListing.query.get_or_404(listing_id)
    now = datetime.now(timezone.utc)
    safe_dt = listing.safe_until.replace(tzinfo=timezone.utc) if listing.safe_until.tzinfo is None else listing.safe_until

    # 4. Confirm listing is Available
    # 5. Confirm safe_until has not expired
    # 6. Confirm food safety requirements
    if listing.status != 'Available' or listing.quantity_portions <= 0 or safe_dt <= now or not listing.fssai_verified:
        flash("This food listing is no longer available or has expired.", "warning")
        return redirect(url_for('donation.marketplace'))

    beneficiaries_raw = request.form.get('beneficiaries_count', '').strip()
    notes = request.form.get('notes', '').strip()

    # 7. Confirm requested portions are valid
    # 8. Confirm requested portions <= available portions
    try:
        beneficiaries_count = int(beneficiaries_raw)
        if beneficiaries_count <= 0:
            flash("Requested beneficiary portion count must be greater than 0.", "warning")
            return redirect(url_for('donation.marketplace'))
        if beneficiaries_count > listing.quantity_portions:
            flash(f"Requested portions ({beneficiaries_count}) cannot exceed available quantity ({listing.quantity_portions}).", "warning")
            return redirect(url_for('donation.marketplace'))
    except (ValueError, TypeError):
        flash("Please enter a valid numeric portion count.", "warning")
        return redirect(url_for('donation.marketplace'))

    if not notes:
        flash("Please provide distribution notes or target community details.", "warning")
        return redirect(url_for('donation.marketplace'))

    # 9. Confirm NGO city == listing pickup_city (case-insensitive and whitespace-normalized)
    if not current_user.city or not cities_match(current_user.city, listing.pickup_city):
        ngo_city_display = current_user.city.strip() if current_user.city else "Not Configured"
        flash(f"Location restriction: You can only claim surplus food available in your operating city ({ngo_city_display}).", "danger")
        return redirect(url_for('donation.marketplace'))

    # All checks passed: Generate OTP and atomically reserve portions
    otp = generate_verification_otp()

    try:
        # Atomic deduction to prevent over-claiming
        listing.quantity_portions -= beneficiaries_count
        if listing.quantity_portions == 0:
            listing.status = 'Claimed'

        claim = Claim(
            listing_id=listing.id,
            ngo_id=current_user.id,
            beneficiaries_count=beneficiaries_count,
            status='Claimed',
            verification_otp=otp,
            notes=notes
        )
        db.session.add(claim)
        db.session.commit()

        flash(f"Success! You claimed {beneficiaries_count} portions of {listing.food_name}. Your 6-Digit Pickup Verification OTP is: {otp}. Present this during collection at the kitchen gate.", "success")
        return redirect(url_for('donation.tracking'))
    except Exception:
        db.session.rollback()
        flash("A database error occurred while reserving your claim. Please try again.", "danger")
        return redirect(url_for('donation.marketplace'))

@donation_bp.route('/tracking')
@login_required
def tracking():
    # If NGO, show only claims made by this NGO; If Kitchen Manager, show only claims for their listings
    if current_user.role == 'ngo':
        claims = Claim.query.filter_by(ngo_id=current_user.id).order_by(Claim.claimed_at.desc()).all()
    elif current_user.role == 'kitchen_manager':
        claims = Claim.query.join(SurplusListing).filter(SurplusListing.donor_id == current_user.id).order_by(Claim.claimed_at.desc()).all()
    else:
        claims = []

    return render_template('redistribution/tracking.html', claims=claims)

@donation_bp.route('/verify-otp/<int:claim_id>', methods=['POST'])
@login_required
@kitchen_manager_required
def verify_otp(claim_id):
    claim = Claim.query.get_or_404(claim_id)

    # Authorization guard: Kitchen Manager can only verify claims for their own surplus
    if claim.listing.donor_id != current_user.id:
        flash("Access denied: You can only verify claims for surplus food broadcast from your kitchen.", "danger")
        return redirect(url_for('donation.tracking'))

    if claim.status == 'Delivered':
        flash("This claim has already been verified and delivered.", "info")
        return redirect(url_for('donation.tracking'))

    entered_otp = request.form.get('otp', '').strip()

    if not entered_otp or not entered_otp.isdigit() or len(entered_otp) != 6:
        flash("Verification OTP must be exactly 6 numeric digits.", "warning")
        return redirect(url_for('donation.tracking'))

    if entered_otp == claim.verification_otp:
        claim.status = 'Delivered'
        claim.delivered_at = datetime.now(timezone.utc)
        # Check if parent listing has 0 remaining portions and all its claims are delivered
        all_claims_delivered = all(c.status == 'Delivered' for c in claim.listing.claims)
        if claim.listing.quantity_portions == 0 and all_claims_delivered:
            claim.listing.status = 'Completed'
        db.session.commit()
        flash(f"OTP Verified! Delivery of {claim.beneficiaries_count} meals confirmed and credited to the ESG sustainability ledger.", "success")
    else:
        flash("Invalid OTP entered. Please verify the 6-digit code with the receiving NGO representative.", "danger")

    return redirect(url_for('donation.tracking'))

