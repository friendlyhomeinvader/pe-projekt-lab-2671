import itertools

import pytest

from app import db
from app.models.user import User
from app.services.preferences import is_installed, mark_installed
from tests.mock_db import assert_database_is_isolated, create_isolated_app

_login_counter = itertools.count()

DEFAULT_PASSWORD = "Password123456!!"


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


@pytest.fixture
def login_as(client):
    """Create a user with the given role and authenticate `client` as them.

    Role-agnostic so any test can exercise role-gated routes/APIs without
    each one hand-rolling a user + session. Returns the created `User`
    (e.g. to assert ownership); the shared `client` fixture carries the
    session cookie for subsequent requests.

        def test_x(client, login_as):
            user = login_as("REQUESTER")
            response = client.get(...)
    """

    def _login_as(role, *, password=DEFAULT_PASSWORD, **overrides):
        if not is_installed():
            mark_installed()

        n = next(_login_counter)
        defaults = {
            "username": f"test.{role.lower()}.{n}",
            "display_name": f"Test {role.title()} {n}",
            "email": f"test.{role.lower()}.{n}@uni.su",
        }
        defaults.update(overrides)

        user = User(role=role, **defaults)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        response = client.post(
            "/login",
            data={"username": user.username, "password": password},
        )
        assert response.status_code == 302 and response.location == "/", (
            f"login as {role} failed: {response.status_code} -> {response.location!r}"
        )

        return user

    return _login_as
