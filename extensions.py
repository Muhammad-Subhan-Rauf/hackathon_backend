# extensions.py
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Initialize extensions here, but don't bind them to the app yet.
# The binding will happen in the main app.py file.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)