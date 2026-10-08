import pytest

from app import db
from tests.mock_db import assert_database_is_isolated, create_isolated_app


@pytest.fixture
def app(tmp_path, monkeypatch):
    flask_app = create_isolated_app(tmp_path, monkeypatch)

    with flask_app.app_context():
        assert_database_is_isolated(flask_app)
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
