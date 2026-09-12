from datetime import datetime, timezone, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import SurplusListing, Claim
from app.services.redistribution import generate_verification_otp, calculate_listing_urgency, match_listings_for_ngo

donation_bp = Blueprint('donation', __name__)

@donation_bp.route('/list', methods=['GET', 'POST'])
@login_required
def list_surplus():
    if request.method == 'POST':
        food_name = request.form.get('food_name', '').strip()
        quantity_portions = int(request.form.get('quantity_portions', 0))
        weight_approx_kg = float(request.form.get('weight_approx_kg', 0.0))
        dietary_type = request.form.get('dietary_type', 'Vegetarian')
        packaging_type = request.form.get('packaging_type', 'Food-Grade Steel Containers')
        storage_temp = request.form.get('storage_temp', 'Hot (>60°C)')
        safe_hours = float(request.form.get('safe_hours', 4.0))
        pickup_address = request.form.get('pickup_address', current_user.address or '').strip()
        contact_phone = request.form.get('contact_phone', current_user.contact_phone or '').strip()
        fssai_verified = bool(request.form.get('fssai_verified'))

        now = datetime.now(timezone.utc)
        safe_until = now + timedelta(hours=safe_hours)

        listing = SurplusListing(
            food_name=food_name,
            quantity_portions=quantity_portions,
            weight_approx_kg=weight_approx_kg,
            dietary_type=dietary_type,
            prepared_time=now,
            safe_until=safe_until,
            packaging_type=packaging_type,
            storage_temp=storage_temp,
            pickup_address=pickup_address or "Campus Mess Kitchen, Gate 2",
            contact_phone=contact_phone or "+91 98765 00000",
            fssai_verified=fssai_verified,
            status='Available',
            donor_id=current_user.id
        )
        db.session.add(listing)
        db.session.commit()

        flash(f"Surplus broadcast created for '{food_name}' ({quantity_portions} portions). Nearby NGOs notified!", "success")
        return redirect(url_for('donation.marketplace'))

    return render_template('redistribution/list_surplus.html')

@donation_bp.route('/marketplace')
@login_required
def marketplace():
    listings = SurplusListing.query.order_by(SurplusListing.created_at.desc()).all()
    
    # Process urgency scores for display
    cards = []
    for l in listings:
        urgency = calculate_listing_urgency(l.safe_until)
        cards.append({
            'listing': l,
            'urgency': urgency
        })

    return render_template('redistribution/marketplace.html', cards=cards)

@donation_bp.route('/claim/<int:listing_id>', methods=['POST'])
@login_required
def claim_listing(listing_id):
    listing = SurplusListing.query.get_or_404(listing_id)
    if listing.status != 'Available':
        flash("This food listing has already been claimed or expired.", "warning")
        return redirect(url_for('donation.marketplace'))

    beneficiaries_count = int(request.form.get('beneficiaries_count', listing.quantity_portions))
    notes = request.form.get('notes', '').strip()
    otp = generate_verification_otp()

    claim = Claim(
        listing_id=listing.id,
        ngo_id=current_user.id,
        beneficiaries_count=beneficiaries_count,
        status='Claimed',
        verification_otp=otp,
        notes=notes
    )
    listing.status = 'Claimed'
    db.session.add(claim)
    db.session.commit()

    flash(f"Success! You claimed {listing.food_name}. Your Verification OTP is: {otp}. Present this during pickup.", "success")
    return redirect(url_for('donation.tracking'))

@donation_bp.route('/tracking')
@login_required
def tracking():
    # If NGO, show claims made by NGO; If kitchen manager, show claims for donor's listings
    if current_user.role == 'ngo':
        claims = Claim.query.filter_by(ngo_id=current_user.id).order_by(Claim.claimed_at.desc()).all()
    else:
        claims = Claim.query.join(SurplusListing).filter(SurplusListing.donor_id == current_user.id).order_by(Claim.claimed_at.desc()).all()

    return render_template('redistribution/tracking.html', claims=claims)

@donation_bp.route('/verify-otp/<int:claim_id>', methods=['POST'])
@login_required
def verify_otp(claim_id):
    claim = Claim.query.get_or_404(claim_id)
    entered_otp = request.form.get('otp', '').strip()

    if entered_otp == claim.verification_otp:
        claim.status = 'Delivered'
        claim.delivered_at = datetime.now(timezone.utc)
        claim.listing.status = 'Completed'
        db.session.commit()
        flash("OTP verified! Delivery confirmed and recorded in the ESG impact ledger.", "success")
    else:
        flash("Invalid OTP entered. Please verify with the receiving NGO representative.", "danger")

    return redirect(url_for('donation.tracking'))
