# models.py
import uuid
from datetime import datetime, time
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# New model to store revoked JWT tokens for logout functionality
class TokenBlocklist(db.Model):
    __tablename__ = 'token_blocklist'
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.Text, unique=True, nullable=False)
    full_name = db.Column(db.Text, nullable=False)
    major = db.Column(db.Text)
    year = db.Column(db.Integer)
    phone_number = db.Column(db.Text)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.Text, db.CheckConstraint("role IN ('driver', 'rider', 'both')"), nullable=False, default='rider')
    
    # New fields for driver location
    current_lat = db.Column(db.Float, nullable=True)
    current_lng = db.Column(db.Float, nullable=True)
    last_location_update = db.Column(db.DateTime, nullable=True)
    
    avg_driver_rating = db.Column(db.Float, default=5.0)
    driver_rating_count = db.Column(db.Integer, default=0)
    avg_rider_rating = db.Column(db.Float, default=5.0)
    rider_rating_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    rides_driven = db.relationship('Ride', backref='driver', lazy=True, foreign_keys='Ride.driver_id')
    bookings = db.relationship('Booking', backref='rider', lazy=True, foreign_keys='Booking.rider_id')
    ratings_given = db.relationship('Rating', backref='reviewer', lazy=True, foreign_keys='Rating.reviewer_id')
    ratings_received = db.relationship('Rating', backref='reviewee', lazy=True, foreign_keys='Rating.reviewee_id')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Ride(db.Model):
    __tablename__ = 'rides'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    driver_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    origin_name = db.Column(db.Text, nullable=False)
    origin_lat = db.Column(db.Float)
    origin_lng = db.Column(db.Float)
    destination_name = db.Column(db.Text, nullable=False)
    destination_lat = db.Column(db.Float)
    destination_lng = db.Column(db.Float)
    departure_time = db.Column(db.DateTime, nullable=False)
    total_seats = db.Column(db.Integer, nullable=False)
    available_seats = db.Column(db.Integer, nullable=False)
    route_polyline = db.Column(db.Text)
    status = db.Column(db.Text, db.CheckConstraint("status IN ('scheduled', 'in_progress', 'completed', 'cancelled')"), default='scheduled')
    is_recurring = db.Column(db.Boolean, default=False)
    recurring_id = db.Column(db.String(36), db.ForeignKey('recurring_rides.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    bookings = db.relationship('Booking', backref='ride', lazy=True, cascade="all, delete-orphan")

class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ride_id = db.Column(db.String(36), db.ForeignKey('rides.id'), nullable=False)
    rider_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    pickup_point_name = db.Column(db.Text, nullable=False)
    pickup_point_lat = db.Column(db.Float)
    pickup_point_lng = db.Column(db.Float)
    status = db.Column(db.Text, db.CheckConstraint("status IN ('requested', 'confirmed', 'cancelled_by_rider', 'completed')"), default='confirmed')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('ride_id', 'rider_id', name='_ride_rider_uc'),)

class Rating(db.Model):
    __tablename__ = 'ratings'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ride_id = db.Column(db.String(36), db.ForeignKey('rides.id'), nullable=False)
    reviewer_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)
    reviewee_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    rating_type = db.Column(db.Text, db.CheckConstraint("rating_type IN ('driver_rating', 'rider_rating')"), nullable=False)
    rating_value = db.Column(db.Integer, db.CheckConstraint('rating_value >= 1 AND rating_value <= 5'), nullable=False)
    review_text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# NEW MODEL: To store the template for a recurring ride
class RecurringRide(db.Model):
    __tablename__ = 'recurring_rides'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    driver_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    origin_name = db.Column(db.Text, nullable=False)
    origin_lat = db.Column(db.Float)
    origin_lng = db.Column(db.Float)
    destination_name = db.Column(db.Text, nullable=False)
    destination_lat = db.Column(db.Float)
    destination_lng = db.Column(db.Float)
    # Store departure time without date, e.g., 08:00:00
    departure_time_of_day = db.Column(db.Time, nullable=False)
    # Store days as a comma-separated string, e.g., "0,1,2,3,4" for Mon-Fri
    days_of_week = db.Column(db.String(15), nullable=False)
    total_seats = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# NEW MODEL: For pattern recognition
class UserTripPattern(db.Model):
    __tablename__ = 'user_trip_patterns'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    origin_name = db.Column(db.Text, nullable=False)
    destination_name = db.Column(db.Text, nullable=False)
    trip_count = db.Column(db.Integer, default=1)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'origin_name', 'destination_name', name='_user_trip_uc'),)