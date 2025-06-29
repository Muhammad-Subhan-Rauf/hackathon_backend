# config.py
import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'a-very-secret-key-that-you-should-change')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///carpool.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    RATELIMIT_ENABLED = False

    # Flask-JWT-Extended settings
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'another-super-secret-key')
    # Use shorter-lived access tokens for better security
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    # Use longer-lived refresh tokens for better user experience
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    # Enable blocklisting to allow for token revocation (logout)
    JWT_BLOCKLIST_ENABLED = True
    JWT_BLOCKLIST_TOKEN_CHECKS = ['access', 'refresh']