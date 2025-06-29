# routes/users_routes.py
from flask import Blueprint, request, jsonify
from models import db, User, TokenBlocklist, Ride, Booking
from flask_jwt_extended import (
    create_access_token, create_refresh_token, jwt_required,
    get_jwt_identity, get_jwt
)
from werkzeug.security import check_password_hash
import re
from extensions import limiter
from auth_decorators import driver_required
from datetime import datetime

users_bp = Blueprint('users_bp', __name__)

# Allowed email domains from the project spec
ALLOWED_DOMAINS = ["formanite.fccollege.edu.pk", "fccollege.edu.pk"]

@users_bp.route("/auth/register", methods=["POST"])
@limiter.limit("10 per hour") # Rate limit registration attempts
def register():
    data = request.get_json()
    email = data.get('email', '').lower()
    password = data.get('password')
    full_name = data.get('fullName')

    if not all([email, password, full_name]):
        return jsonify({"error": "Missing required fields"}), 400
    
    # REQUIREMENT: Verified university email
    if not any(email.endswith(domain) for domain in ALLOWED_DOMAINS):
        return jsonify({"error": "Registration is only allowed for university emails."}), 400

    # Add basic password strength validation
    if len(password) < 8 or not re.search("[a-zA-Z]", password) or not re.search("[0-9]", password):
        return jsonify({"error": "Password must be at least 8 characters and contain both letters and numbers."}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    new_user = User(email=email, full_name=full_name)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "User registered successfully", "user_id": new_user.id}), 201

@users_bp.route("/auth/login", methods=["POST"])
@limiter.limit("5 per minute") # Stricter rate limit for login to prevent brute-forcing
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid credentials"}), 401

    # Create both access and refresh tokens for the user
    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)
    return jsonify(access_token=access_token, refresh_token=refresh_token)

@users_bp.route("/auth/refresh", methods=["POST"])
@jwt_required(refresh=True) # This route requires a valid refresh token
def refresh():
    current_user_id = get_jwt_identity()
    new_access_token = create_access_token(identity=current_user_id)
    return jsonify(access_token=new_access_token)

@users_bp.route("/auth/logout", methods=["POST"])
@jwt_required()
def logout():
    # To properly log out, we add the token's JTI (JWT ID) to the blocklist.
    jti = get_jwt()["jti"]
    revoked_token = TokenBlocklist(jti=jti)
    db.session.add(revoked_token)
    db.session.commit()
    # The client is responsible for discarding the refresh token upon logout.
    return jsonify({"message": "Access token has been revoked."})


@users_bp.route("/users/me", methods=["GET"])
@jwt_required()
def get_my_profile():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    return jsonify({
        "id": user.id, "email": user.email, "full_name": user.full_name,
        "major": user.major, "year": user.year, "phone_number": user.phone_number,
        "role": user.role, "avg_driver_rating": user.avg_driver_rating,
        "driver_rating_count": user.driver_rating_count,
        "avg_rider_rating": user.avg_rider_rating,
        "rider_rating_count": user.rider_rating_count,
        "current_lat": user.current_lat,
        "current_lng": user.current_lng,
        "last_location_update": user.last_location_update.isoformat() if user.last_location_update else None
    })

@users_bp.route("/users/me", methods=["PUT"])
@jwt_required()
def update_my_profile():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    data = request.get_json()
    user.full_name = data.get('full_name', user.full_name)
    user.major = data.get('major', user.major)
    user.year = data.get('year', user.year)
    user.phone_number = data.get('phone_number', user.phone_number)
    user.role = data.get('role', user.role)
    
    db.session.commit()
    return jsonify({"message": "Profile updated successfully"})

@users_bp.route("/users/me/location", methods=["PUT"])
@driver_required
def update_my_location():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    data = request.get_json()
    lat = data.get('lat')
    lng = data.get('lng')

    if lat is None or lng is None:
        return jsonify({"error": "Latitude (lat) and longitude (lng) are required"}), 400
    
    try:
        user.current_lat = float(lat)
        user.current_lng = float(lng)
        user.last_location_update = datetime.utcnow()
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid latitude or longitude format"}), 400

    db.session.commit()
    return jsonify({"message": "Location updated successfully"})

@users_bp.route("/users/<string:id>", methods=["GET"])
def get_user_profile(id):
    user = User.query.get(id)
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    # Return only public information
    return jsonify({
        "id": user.id, "full_name": user.full_name,
        "major": user.major, "year": user.year, "role": user.role,
        "avg_driver_rating": user.avg_driver_rating,
        "driver_rating_count": user.driver_rating_count,
        "avg_rider_rating": user.avg_rider_rating,
        "rider_rating_count": user.rider_rating_count,
    })

# --- NEW ENDPOINT ---
@users_bp.route("/users/me/rides", methods=["GET"])
@jwt_required()
def get_my_rides():
    current_user_id = get_jwt_identity()
    
    # Rides where the user is the driver
    driving_rides = Ride.query.filter(
        Ride.driver_id == current_user_id,
        Ride.status.in_(['scheduled', 'in_progress'])
    ).order_by(Ride.departure_time).all()

    # Rides where the user is a passenger
    riding_bookings = Booking.query.join(Ride).filter(
        Booking.rider_id == current_user_id,
        Booking.status == 'confirmed',
        Ride.status.in_(['scheduled', 'in_progress'])
    ).order_by(Ride.departure_time).all()
    
    riding_rides = [b.ride for b in riding_bookings]

    def serialize_ride(r):
        return {
            "id": r.id, 
            "origin_name": r.origin_name, 
            "destination_name": r.destination_name,
            "departure_time": r.departure_time.isoformat(), 
            "available_seats": r.available_seats,
            "status": r.status
        }

    return jsonify({
        "driving": [serialize_ride(r) for r in driving_rides],
        "riding": [serialize_ride(r) for r in riding_rides]
    })