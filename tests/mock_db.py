import os

from app import create_app, db


def create_isolated_app(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")

    return create_app()


def assert_database_is_isolated(flask_app):
    real_db_path = os.path.normpath(
        os.path.join(flask_app.instance_path, "database", "app.db")
    )
    resolved_db_path = os.path.normpath(str(db.engine.url.database or ""))

    assert resolved_db_path != real_db_path, (
        f"Refusing to run tests against the real database ({resolved_db_path!r}). Tests must use an isolated temp-file database -- see tests/mock_db.py."
    )
