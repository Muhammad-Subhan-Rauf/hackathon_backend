# cleardb.py
import os
import sys

# Ensure the app's directory is in the path to allow imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Now we can import the app and db
from app import app, db
from models import User # Import User model

print("--- Database Reset Script---")

# The app.app_context() is required to interact with the database
with app.app_context():
    print("Dropping all database tables...")
    db.drop_all()
    print("Tables dropped.")
    
    print("Creating all database tables from models...")
    db.create_all()
    print("Tables created.")

    print("\n--- Seeding Test Users ---")
    try:
        # Create Driver User
        driver_email = 'driver@test.com'
        if not User.query.filter_by(email=driver_email).first():
            test_driver = User(
                email=driver_email,
                full_name='Test Driver',
                role='driver'
            )
            test_driver.set_password('123')
            db.session.add(test_driver)
            print(f"  - Created user: {driver_email}")

        # Create Rider User
        rider_email = 'rider@test.com'
        if not User.query.filter_by(email=rider_email).first():
            test_rider = User(
                email=rider_email,
                full_name='Test Rider',
                role='rider' # The default is 'rider', but being explicit is good
            )
            test_rider.set_password('123')
            db.session.add(test_rider)
            print(f"  - Created user: {rider_email}")
            
        db.session.commit()
        print("Test users seeded successfully.")
    except Exception as e:
        db.session.rollback()
        print(f"An error occurred while seeding users: {e}")


print("\n✅ Database has been successfully reset and seeded.")