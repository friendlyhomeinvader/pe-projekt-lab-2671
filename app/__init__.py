import os

from apiflask import APIFlask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)
migrate = Migrate()
login_manager = LoginManager()


def create_app():
    app = APIFlask(
        __name__, instance_relative_config=True, title="Keymaster API", version="0.1.1"
    )

    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///database/app.db"
    )
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "dashboard"

    from app.api import register_api
    from app.models.user import User
    from app.routes import register_routes

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.get("/health")
    def check_health():
        return {"status": "ok"}

    @app.get("/db-health")
    def db_health():
        tables = db.inspect(db.engine).get_table_names()
        return {"database-status": "ok", "tables": tables}

    register_api(app)
    register_routes(app)

    @app.spec_processor
    def hide_non_api_paths(spec):
        spec["paths"] = {
            path: item
            for path, item in spec["paths"].items()
            if path.startswith("/api/")
        }
        return spec

    return app
