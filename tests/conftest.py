import pytest

from app import create_app

@pytest.fixture
def app():
    flask_app = create_app()
    return flask_app

@pytest.fixture
def client(app):
    return app.test_client()
