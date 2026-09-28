import os

from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)
migrate = Migrate()


def create_app():
    app = Flask(__name__, instance_relative_config=True)

    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///database/app.db")

    db.init_app(app)
    migrate.init_app(app, db)

    from app import models

    @app.get("/health")
    def check_health():
        return {"status": "ok"}

    @app.get("/db-health")
    def db_health():
        tables = db.inspect(db.engine).get_table_names()
        return {"database-status": "ok", "tables": tables}

    return app
