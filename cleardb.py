# cleardb.py
import os
import sys

# Ensure the app's directory is in the path to allow imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Now we can import the app and db
from app import app, db

print("--- Database Reset Script---")

# The app.app_context() is required to interact with the database
with app.app_context():
    print("Dropping all database tables...")
    db.drop_all()
    print("Tables dropped.")
    
    print("Creating all database tables from models...")
    db.create_all()
    print("Tables created.")

print("\n✅ Database has been successfully reset to the current schema.")