# routes/rides_routes.py
from flask import Blueprint, request, jsonify
from models import db, Ride, Booking, User, Rating, RecurringRide
from flask_jwt_extended import get_jwt_identity, jwt_required
from auth_decorators import driver_required, rider_required
from datetime import datetime, timedelta, date, time
from sqlalchemy import desc, func
import math

# Import the helper function from features_routes
# Use a relative import within the package
from .features_routes import _update_trip_patterns

rides_bp = Blueprint('rides_bp', __name__)

# Helper function for penalty ratings
def _apply_penalty_rating(user_id, ride_id, penalty_rating, rating_type, review_text):
    user = User.query.get(user_id)
    if not user:
        return

    new_rating = Rating(
        ride_id=ride_id,
        reviewer_id=None, # System-generated
        reviewee_id=user_id,
        rating_type=rating_type,
        rating_value=penalty_rating,
        review_text=review_text
    )
    
    if rating_type == 'driver_rating':
        old_total = user.avg_driver_rating * user.driver_rating_count
        user.driver_rating_count += 1
        user.avg_driver_rating = (old_total + penalty_rating) / user.driver_rating_count
    else: # rider_rating
        old_total = user.avg_rider_rating * user.rider_rating_count
        user.rider_rating_count += 1
        user.avg_rider_rating = (old_total + penalty_rating) / user.rider_rating_count
        
    db.session.add(new_rating)

@rides_bp.route("/rides", methods=["POST"])
@driver_required
def create_ride():
    driver_id = get_jwt_identity()
    data = request.get_json()
    departure_time = datetime.fromisoformat(data['departure_time'])

    if not (6 <= departure_time.hour <= 22):
        return jsonify({"error": "Rides can only be scheduled between 6:00 AM and 10:00 PM."}), 400

    new_ride = Ride(
        driver_id=driver_id,
        origin_name=data['origin_name'],
        origin_lat=data.get('origin_lat'),
        origin_lng=data.get('origin_lng'),
        destination_name=data['destination_name'],
        destination_lat=data.get('destination_lat'),
        destination_lng=data.get('destination_lng'),
        departure_time=departure_time,
        total_seats=data['total_seats'],
        available_seats=data['total_seats']
    )
    db.session.add(new_ride)
    db.session.commit()
    return jsonify({"message": "Ride created", "ride_id": new_ride.id}), 201

@rides_bp.route("/rides", methods=["GET"])
def search_rides():
    dest = request.args.get('destination')
    origin = request.args.get('origin')
    time_str = request.args.get('time')
    window_minutes = request.args.get('window_minutes', 30, type=int)
    sort_by = request.args.get('sort_by')
    
    # Coordinate-based search parameters
    origin_lat = request.args.get('origin_lat', type=float)
    origin_lng = request.args.get('origin_lng', type=float)
    dest_lat = request.args.get('dest_lat', type=float)
    dest_lng = request.args.get('dest_lng', type=float)
    radius_km = 1.0

    query = Ride.query.filter(Ride.status.in_(['scheduled', 'in_progress']))

    # --- Coordinate-based search takes precedence ---
    if origin_lat is not None and origin_lng is not None:
        # Haversine formula to find rides with origin within 1km radius
        origin_lat_rad = math.radians(origin_lat)
        
        ride_origin_lat_rad = Ride.origin_lat * (math.pi / 180.0)
        dlat_origin = ride_origin_lat_rad - origin_lat_rad
        dlng_origin = (Ride.origin_lng * (math.pi / 180.0)) - math.radians(origin_lng)
        
        # FIX: Use multiplication instead of the power operator (**)
        a_origin = func.sin(dlat_origin / 2) * func.sin(dlat_origin / 2) + \
                   func.cos(origin_lat_rad) * func.cos(ride_origin_lat_rad) * \
                   func.sin(dlng_origin / 2) * func.sin(dlng_origin / 2)
        c_origin = 2 * func.atan2(func.sqrt(a_origin), func.sqrt(1 - a_origin))
        distance_km_origin = 6371 * c_origin # Earth radius in km
        
        query = query.filter(Ride.origin_lat != None, Ride.origin_lng != None, distance_km_origin <= radius_km)
    elif origin:
        # Fallback to text search if no origin coordinates
        query = query.filter(Ride.origin_name.ilike(f"%{origin}%"))

    if dest_lat is not None and dest_lng is not None:
        # Haversine formula for destination
        dest_lat_rad = math.radians(dest_lat)
        
        ride_dest_lat_rad = Ride.destination_lat * (math.pi / 180.0)
        dlat_dest = ride_dest_lat_rad - dest_lat_rad
        dlng_dest = (Ride.destination_lng * (math.pi / 180.0)) - math.radians(dest_lng)

        # FIX: Use multiplication instead of the power operator (**)
        a_dest = func.sin(dlat_dest / 2) * func.sin(dlat_dest / 2) + \
                 func.cos(dest_lat_rad) * func.cos(ride_dest_lat_rad) * \
                 func.sin(dlng_dest / 2) * func.sin(dlng_dest / 2)
        c_dest = 2 * func.atan2(func.sqrt(a_dest), func.sqrt(1 - a_dest))
        distance_km_dest = 6371 * c_dest

        query = query.filter(Ride.destination_lat != None, Ride.destination_lng != None, distance_km_dest <= radius_km)
    elif dest:
        # Fallback to text search if no destination coordinates
        query = query.filter(Ride.destination_name.ilike(f"%{dest}%"))
    
    if time_str:
        try:
            center_time = datetime.fromisoformat(time_str)
            start_time = center_time - timedelta(minutes=window_minutes)
            end_time = center_time + timedelta(minutes=window_minutes)
            query = query.filter(Ride.departure_time.between(start_time, end_time))
        except ValueError:
            return jsonify({"error": "Invalid time format. Please use ISO 8601 format."}), 400

    if sort_by == 'rating':
        query = query.join(User, Ride.driver_id == User.id).order_by(desc(User.avg_driver_rating))
    else:
        query = query.order_by(Ride.departure_time)

    rides = query.all()
    
    return jsonify([{
        "id": r.id, "driver_id": r.driver_id, "origin_name": r.origin_name,
        "destination_name": r.destination_name, "departure_time": r.departure_time.isoformat(),
        "available_seats": r.available_seats
    } for r in rides])

@rides_bp.route("/rides/<string:id>", methods=["GET"])
@jwt_required(optional=True)
def get_ride_details(id):
    ride = Ride.query.get_or_404(id)
    driver = User.query.get(ride.driver_id)
    bookings = Booking.query.filter_by(ride_id=id).all()
    
    # Check which users the current user has already rated for this ride
    ratings_given_by_me = []
    current_user_id = get_jwt_identity()
    if current_user_id:
        ratings = Rating.query.filter_by(ride_id=id, reviewer_id=current_user_id).all()
        ratings_given_by_me = [r.reviewee_id for r in ratings]
        
    return jsonify({
        "id": ride.id, "origin_name": ride.origin_name, "destination_name": ride.destination_name,
        "departure_time": ride.departure_time.isoformat(), "total_seats": ride.total_seats,
        "available_seats": ride.available_seats, "status": ride.status,
        "driver": {"id": driver.id, "full_name": driver.full_name, "avg_driver_rating": driver.avg_driver_rating},
        "bookings": [
            {
                "id": b.id,
                "status": b.status,
                "rider": {
                    "id": b.rider.id,
                    "full_name": b.rider.full_name,
                    "avg_rider_rating": b.rider.avg_rider_rating
                }
            } for b in bookings
        ],
        "ratings_given_by_me": ratings_given_by_me
    })

@rides_bp.route("/rides/<string:id>", methods=["PUT"])
@driver_required
def update_ride(id):
    ride = Ride.query.get_or_404(id)
    if ride.driver_id != get_jwt_identity():
        return jsonify({"error": "You are not the driver of this ride"}), 403
    
    data = request.get_json()
    new_status = data.get('status')
    
    if new_status:
        # Prevent moving backwards from a final state
        if ride.status in ['completed', 'cancelled']:
            return jsonify({"error": f"Cannot change status from '{ride.status}'"}), 400
        
        # When ride is completed, log trip patterns for all participants
        if new_status == 'completed' and ride.status != 'completed':
            _update_trip_patterns(ride)
            # Also update booking statuses to 'completed'
            Booking.query.filter_by(ride_id=ride.id, status='confirmed').update({'status': 'completed'})
            
        ride.status = new_status
        
    db.session.commit()
    return jsonify({"message": "Ride updated"})

@rides_bp.route("/rides/<string:id>", methods=["DELETE"])
@driver_required
def cancel_ride(id):
    ride = Ride.query.get_or_404(id)
    driver_id = get_jwt_identity()
    if ride.driver_id != driver_id:
        return jsonify({"error": "You are not the driver of this ride"}), 403
    
    if ride.status != 'scheduled':
        return jsonify({"error": "Only scheduled rides can be cancelled."}), 400

    ride.status = 'cancelled'
    _apply_penalty_rating(
        driver_id, ride.id, 1, 'driver_rating', 'Automatic 1-star rating for cancelling a ride.'
    )
    db.session.commit()
    return jsonify({"message": "Ride cancelled and penalty applied"})

@rides_bp.route("/rides/<string:id>/bookings", methods=["POST"])
@jwt_required()
def book_seat(id):
    ride = Ride.query.get_or_404(id)
    rider_id = get_jwt_identity()
    user = User.query.get(rider_id)

    if ride.driver_id == rider_id:
        return jsonify({"error": "Driver cannot book their own ride"}), 400

    if not user or user.role not in ['rider', 'both']:
        return jsonify({"error": "Access forbidden: Your role does not permit booking rides."}), 403

    if ride.available_seats <= 0:
        return jsonify({"error": "No available seats"}), 400
    if Booking.query.filter_by(ride_id=id, rider_id=rider_id).first():
        return jsonify({"error": "You have already booked this ride"}), 409

    data = request.get_json()
    new_booking = Booking(
        ride_id=id,
        rider_id=rider_id,
        pickup_point_name=data['pickup_point_name']
    )
    ride.available_seats -= 1
    db.session.add(new_booking)
    db.session.commit()
    return jsonify({"message": "Booking confirmed", "booking_id": new_booking.id}), 201

@rides_bp.route("/bookings/<string:id>", methods=["DELETE"])
@jwt_required()
def cancel_booking(id):
    booking = Booking.query.get_or_404(id)
    current_user_id = get_jwt_identity()
    ride = Ride.query.get(booking.ride_id)

    if booking.rider_id != current_user_id:
        return jsonify({"error": "You cannot cancel this booking"}), 403
    
    if ride.status != 'scheduled':
        return jsonify({"error": "Cannot cancel a booking for a ride that is not scheduled."}), 400
        
    message = "Booking cancelled"
    time_until_departure = ride.departure_time - datetime.utcnow()
    if time_until_departure < timedelta(hours=1) and ride.status == 'scheduled':
            _apply_penalty_rating(
            current_user_id, ride.id, 2, 'rider_rating', 'Automatic 2-star rating for late cancellation (<1 hour before departure).'
        )
            message = "Booking cancelled with penalty for late cancellation"

    booking.status = 'cancelled_by_rider'
    ride.available_seats += 1
    db.session.commit()
    return jsonify({"message": message})

@rides_bp.route("/rides/<string:id>/driver-location", methods=["GET"])
@jwt_required()
def get_driver_location(id):
    ride = Ride.query.get_or_404(id)
    current_user_id = get_jwt_identity()

    # Authorization: User must be a confirmed rider.
    is_confirmed_rider = Booking.query.filter_by(
        ride_id=id, 
        rider_id=current_user_id, 
        status='confirmed'
    ).first()

    if not is_confirmed_rider:
        return jsonify({"error": "You are not authorized to view this ride's location."}), 403

    # Feature should only be active when ride is in progress
    if ride.status != 'in_progress':
        return jsonify({"error": "Live location is only available for rides that are in progress."}), 404

    driver = User.query.get(ride.driver_id)
    if not driver or driver.current_lat is None or driver.current_lng is None:
        return jsonify({"error": "Driver location is not available at the moment."}), 404

    return jsonify({
        "lat": driver.current_lat,
        "lng": driver.current_lng,
        "last_update": driver.last_location_update.isoformat() if driver.last_location_update else None
    })


@rides_bp.route("/rides/recurring", methods=["POST"])
@driver_required
def create_recurring_ride():
    driver_id = get_jwt_identity()
    data = request.get_json()
    departure_time_of_day_str = data['departure_time_of_day'] 
    days_of_week_list = [str(d) for d in data['days_of_week']]

    try:
        departure_time_obj = time.fromisoformat(departure_time_of_day_str)
    except ValueError:
        return jsonify({"error": "Invalid time format for departure_time_of_day. Use HH:MM:SS."}), 400

    new_recurring_ride = RecurringRide(
        driver_id=driver_id,
        origin_name=data['origin_name'],
        origin_lat=data.get('origin_lat'),
        origin_lng=data.get('origin_lng'),
        destination_name=data['destination_name'],
        destination_lat=data.get('destination_lat'),
        destination_lng=data.get('destination_lng'),
        departure_time_of_day=departure_time_obj,
        days_of_week=",".join(days_of_week_list),
        total_seats=data['total_seats']
    )
    db.session.add(new_recurring_ride)
    db.session.flush()

    today = date.today()
    generated_rides_count = 0
    for i in range(7):
        current_date = today + timedelta(days=i)
        if str(current_date.weekday()) in days_of_week_list:
            departure_datetime = datetime.combine(current_date, departure_time_obj)
            if departure_datetime < datetime.now():
                continue
            ride_instance = Ride(
                driver_id=driver_id,
                origin_name=new_recurring_ride.origin_name,
                origin_lat=new_recurring_ride.origin_lat,
                origin_lng=new_recurring_ride.origin_lng,
                destination_name=new_recurring_ride.destination_name,
                destination_lat=new_recurring_ride.destination_lat,
                destination_lng=new_recurring_ride.destination_lng,
                departure_time=departure_datetime,
                total_seats=data['total_seats'],
                available_seats=data['total_seats'],
                is_recurring=True,
                recurring_id=new_recurring_ride.id
            )
            db.session.add(ride_instance)
            generated_rides_count += 1
            
    db.session.commit()
    return jsonify({
        "message": "Recurring ride created", 
        "recurring_ride_id": new_recurring_ride.id,
        "generated_rides_count": generated_rides_count
    }), 201