import os

from apiflask import APIFlask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)
migrate = Migrate()


def create_app():
    app = APIFlask(
        __name__, instance_relative_config=True, title="Keymaster API", version="0.1.0"
    )

    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///database/app.db"
    )

    db.init_app(app)
    migrate.init_app(app, db)

    from app.api import register_api

    @app.get("/health")
    def check_health():
        return {"status": "ok"}

    @app.get("/db-health")
    def db_health():
        tables = db.inspect(db.engine).get_table_names()
        return {"database-status": "ok", "tables": tables}

    register_api(app)

    return app
