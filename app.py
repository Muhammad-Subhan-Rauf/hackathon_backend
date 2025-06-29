from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
from models import db, TokenBlocklist
from flask_jwt_extended import JWTManager, get_jwt
from flask_migrate import Migrate
from extensions import limiter

# Import Blueprints
from routes.users_routes import users_bp
from routes.rides_routes import rides_bp
from routes.features_routes import features_bp

# --- App Initialization ---
app = Flask(__name__)
app.config.from_object(Config)

# --- Enable CORS ---
CORS(app, origins=["http://localhost:5173"], supports_credentials=True)

# --- Extensions Initialization ---
db.init_app(app)
jwt = JWTManager(app)
migrate = Migrate(app, db)
limiter.init_app(app)

# --- JWT Blocklist Loader ---
@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload: dict) -> bool:
    jti = jwt_payload["jti"]
    token = db.session.query(TokenBlocklist.id).filter_by(jti=jti).scalar()
    return token is not None

# --- Register Blueprints ---
app.register_blueprint(users_bp)
app.register_blueprint(rides_bp)
app.register_blueprint(features_bp)

# --- Global Error Handlers ---
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify(error=f"Rate limit exceeded: {e.description}"), 429

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({"error": "Internal server error"}), 500

# --- CLI Command to create DB ---
@app.cli.command("init_db")
def init_db_command():
    """Creates the database tables."""
    with app.app_context():
        db.create_all()
    print("Initialized the database.")


@app.route('/test', methods=['GET'])
def test_endpoint():
    return jsonify(message="Hello, World"), 200


# --- Run the App ---
if __name__ == '__main__':
    app.run(debug=True)
