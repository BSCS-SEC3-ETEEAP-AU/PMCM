"""Application factory for the thesis platform."""
from flask import Flask
from flask_login import LoginManager
from .models import db, User
from config import Config

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)

    from .modules.auth import auth_bp
    from .modules.projects import projects_bp
    from .modules.competency import competency_bp
    from .modules.recommendation import recommendation_bp
    from .modules.reports import reports_bp
    from .modules.main import main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(competency_bp)
    app.register_blueprint(recommendation_bp)
    app.register_blueprint(reports_bp)

    return app
