"""
Redistribution Engine Service
Handles surplus food matching, urgency priority scoring, and OTP verification workflows.
"""

import random
from datetime import datetime, timezone

def normalize_city(city):
    """
    Normalizes a city string for consistent, case-insensitive comparison:
    - Returns None if city is None, empty, or whitespace.
    - Trims leading/trailing whitespace.
    - Condenses internal consecutive spaces.
    - Converts to lowercase.
    """
    if not city:
        return None
    cleaned = " ".join(str(city).strip().split()).lower()
    return cleaned if cleaned else None

def clean_city_name(city):
    """
    Cleans a city name for storage:
    - Trims leading/trailing whitespace.
    - Condenses multiple spaces into a single space.
    - Title-cases city name for clean UI presentation.
    - Returns cleaned string or None.
    """
    if not city:
        return None
    cleaned = " ".join(str(city).strip().split())
    return cleaned.title() if cleaned else None

def cities_match(city_a, city_b):
    """
    Checks if two city names match (case-insensitive and whitespace-normalized).
    Returns False if either city is None, empty, or whitespace.
    """
    norm_a = normalize_city(city_a)
    norm_b = normalize_city(city_b)
    if not norm_a or not norm_b:
        return False
    return norm_a == norm_b

def generate_verification_otp():
    """Generates a secure 6-digit numeric OTP for pickup delivery confirmation."""
    return f"{random.SystemRandom().randint(100000, 999999)}"

def calculate_listing_urgency(safe_until_dt):
    """
    Calculates the urgency priority and remaining time for a surplus food listing.
    Returns:
      urgency_level: 'Critical (< 2h)', 'Urgent (< 4h)', 'Normal (> 4h)', 'Expired'
      hours_remaining: float
      badge_class: Bootstrap badge CSS class
    """
    now = datetime.now(timezone.utc)
    if safe_until_dt.tzinfo is None:
        # If naive, assume UTC
        diff = safe_until_dt - now.replace(tzinfo=None)
    else:
        diff = safe_until_dt - now

    total_seconds = diff.total_seconds()
    hours_remaining = round(total_seconds / 3600.0, 1)

    if hours_remaining <= 0:
        return {
            'level': 'Expired',
            'hours_remaining': 0,
            'badge_class': 'bg-danger text-white',
            'is_expired': True
        }
    elif hours_remaining <= 2:
        return {
            'level': 'High Urgency (< 2h)',
            'hours_remaining': hours_remaining,
            'badge_class': 'bg-danger text-white',
            'is_expired': False
        }
    elif hours_remaining <= 4:
        return {
            'level': 'Moderate Urgency (< 4h)',
            'hours_remaining': hours_remaining,
            'badge_class': 'bg-warning text-dark',
            'is_expired': False
        }
    else:
        return {
            'level': 'Safe Window (> 4h)',
            'hours_remaining': hours_remaining,
            'badge_class': 'bg-success text-white',
            'is_expired': False
        }

def match_listings_for_ngo(listings, capacity=None):
    """
    Prioritizes surplus listings for an NGO based on:
    1. Status is 'Available'
    2. Urgency (nearest safe_until window first to prevent waste)
    3. Capacity compatibility
    """
    matched = []
    for listing in listings:
        if listing.status != 'Available':
            continue
        urgency = calculate_listing_urgency(listing.safe_until)
        if urgency['is_expired']:
            continue
        
        matched.append({
            'listing': listing,
            'urgency': urgency,
            'fits_capacity': True if capacity is None else (listing.quantity_portions <= capacity)
        })

    # Sort by hours remaining ascending (most urgent first)
    matched.sort(key=lambda item: item['urgency']['hours_remaining'])
    return matched
