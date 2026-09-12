import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure the instance directory exists for SQLite
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(os.path.join(app.root_path, '..', 'ml_models'), exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)

    # Register blueprints
    from app.routes.auth_routes import auth_bp
    from app.routes.kitchen_routes import kitchen_bp
    from app.routes.ai_routes import ai_bp
    from app.routes.donation_routes import donation_bp
    from app.routes.dashboard_routes import dashboard_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(kitchen_bp, url_prefix='/kitchen')
    app.register_blueprint(ai_bp, url_prefix='/ai')
    app.register_blueprint(donation_bp, url_prefix='/donation')
    app.register_blueprint(dashboard_bp)

    return app
