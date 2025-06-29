# routes/features_routes.py
from flask import Blueprint, request, jsonify
from models import db, Rating, User, Ride, Booking, UserTripPattern
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import desc

features_bp = Blueprint('features_bp', __name__)

def _update_trip_patterns(completed_ride: Ride):
    """
    Called when a ride is completed. Logs the trip for the driver and all
    riders to build their frequent trip patterns.
    """
    users_on_ride = [completed_ride.driver]
    confirmed_bookings = Booking.query.filter_by(ride_id=completed_ride.id, status='confirmed').all()
    for booking in confirmed_bookings:
        users_on_ride.append(booking.rider)
    
    for user in users_on_ride:
        if not user: continue
        
        pattern = UserTripPattern.query.filter_by(
            user_id=user.id,
            origin_name=completed_ride.origin_name,
            destination_name=completed_ride.destination_name
        ).first()

        if pattern:
            pattern.trip_count += 1
        else:
            new_pattern = UserTripPattern(
                user_id=user.id,
                origin_name=completed_ride.origin_name,
                destination_name=completed_ride.destination_name
            )
            db.session.add(new_pattern)

@features_bp.route("/ratings", methods=["POST"])
@jwt_required()
def submit_rating():
    reviewer_id = get_jwt_identity()
    data = request.get_json()
    
    ride_id = data.get('ride_id')
    reviewee_id = data.get('reviewee_id')
    rating_value = data.get('rating_value')

    if not all([ride_id, reviewee_id, rating_value]):
        return jsonify({"error": "Missing required fields"}), 400
    
    reviewee = User.query.get_or_404(reviewee_id)
    ride = Ride.query.get_or_404(ride_id)
    
    # --- ADDITION: Prevent duplicate ratings ---
    existing_rating = Rating.query.filter_by(
        ride_id=ride_id,
        reviewer_id=reviewer_id,
        reviewee_id=reviewee_id
    ).first()
    if existing_rating:
        return jsonify({"error": "You have already rated this user for this ride."}), 409

    rating_type = 'driver_rating' if ride.driver_id == reviewee_id else 'rider_rating'

    new_rating = Rating(
        ride_id=ride_id,
        reviewer_id=reviewer_id,
        reviewee_id=reviewee_id,
        rating_type=rating_type,
        rating_value=rating_value,
        review_text=data.get('review_text')
    )

    if rating_type == 'driver_rating':
        old_total = reviewee.avg_driver_rating * reviewee.driver_rating_count
        reviewee.driver_rating_count += 1
        reviewee.avg_driver_rating = (old_total + rating_value) / reviewee.driver_rating_count
    else:
        old_total = reviewee.avg_rider_rating * reviewee.rider_rating_count
        reviewee.rider_rating_count += 1
        reviewee.avg_rider_rating = (old_total + rating_value) / reviewee.rider_rating_count

    db.session.add(new_rating)
    db.session.commit()
    
    return jsonify({"message": "Rating submitted successfully"}), 201

# --- Mock AI Endpoints ---

# THIS FUNCTION IS REMOVED
# @features_bp.route("/ai/parse-location", methods=["GET"])
# def parse_location(): ...

@features_bp.route("/ai/recommendations", methods=["GET"])
@jwt_required()
def get_recommendations():
    rides = Ride.query.filter(Ride.destination_name.ilike('%FCCU%'), Ride.status=='scheduled').limit(5).all()
    return jsonify([{
        "id": r.id, "origin_name": r.origin_name, "destination_name": r.destination_name,
        "departure_time": r.departure_time.isoformat(), "available_seats": r.available_seats
    } for r in rides])

@features_bp.route("/ai/estimate-journey", methods=["GET"])
def estimate_journey():
    origin = request.args.get('origin')
    destination = request.args.get('destination')
    if not origin or not destination:
        return jsonify({"error": "Origin and destination are required"}), 400
        
    return jsonify({
        "estimated_duration_minutes": 25,
        "estimated_distance_km": 10.5
    })

# --- AI ENDPOINT FOR PATTERN-BASED RECOMMENDATIONS ---
@features_bp.route("/ai/recommendations/patterns", methods=["GET"])
@jwt_required()
def get_pattern_recommendations():
    user_id = get_jwt_identity()
    
    frequent_patterns = UserTripPattern.query.filter_by(user_id=user_id)\
        .order_by(desc(UserTripPattern.trip_count))\
        .limit(3).all()

    if not frequent_patterns:
        return jsonify([])

    recommendations = []
    for pattern in frequent_patterns:
        matching_rides = Ride.query.filter(
            Ride.origin_name == pattern.origin_name,
            Ride.destination_name == pattern.destination_name,
            Ride.status == 'scheduled',
            Ride.driver_id != user_id
        ).order_by(Ride.departure_time).limit(2).all()
        
        for ride in matching_rides:
            recommendations.append({
                "id": ride.id,
                "origin_name": ride.origin_name,
                "destination_name": ride.destination_name,
                "departure_time": ride.departure_time.isoformat(),
                "reason": f"Matches your frequent trip from {pattern.origin_name} to {pattern.destination_name}"
            })

    return jsonify(recommendations)