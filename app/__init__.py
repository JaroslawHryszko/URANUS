from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import bcrypt

db = SQLAlchemy()
PASSWORD_HASH = None


def create_app(config_class=None):
    app = Flask(__name__)

    if config_class:
        app.config.from_object(config_class)
    else:
        from app.config import Config
        app.config.from_object(Config)

    # Generate password hash
    global PASSWORD_HASH
    admin_password = app.config.get('ADMIN_PASSWORD', 'admin')
    PASSWORD_HASH = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt())

    # Trust reverse proxy headers (Apache)
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)

    # Iframe-friendly headers
    @app.after_request
    def set_headers(response):
        response.headers['Content-Security-Policy'] = (
            "frame-ancestors 'self' uranus.edu.pl *.uranus.edu.pl "
            "gottlob.frege.ii.uj.edu.pl *.ii.uj.edu.pl"
        )
        response.headers.pop('X-Frame-Options', None)
        return response

    # Context processors
    @app.context_processor
    def inject_globals():
        from datetime import datetime
        return {'datetime': datetime, 'enumerate': enumerate, 'getattr': getattr}

    # Register blueprints
    from app.admin.routes import admin_bp
    from app.experiment.routes import experiment_bp
    from app.api.routes import api_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(experiment_bp)
    app.register_blueprint(api_bp)

    # Create tables
    with app.app_context():
        from app import models  # noqa: F401
        db.create_all()

    return app
