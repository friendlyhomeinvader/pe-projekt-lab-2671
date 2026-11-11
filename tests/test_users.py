import itertools

from app import db
from app.models.user import User
from app.services.user import get_user
from tests.helpers import assert_status

_user_counter = itertools.count()


def _create_user(role, **overrides):
    n = next(_user_counter)
    defaults = {
        "username": f"other.{role.lower()}.{n}",
        "display_name": f"Other {role.title()} {n}",
        "email": f"other.{role.lower()}.{n}@uni.su",
    }
    defaults.update(overrides)
    user = User(role=role, **defaults)
    user.set_password("Password123456!!")
    db.session.add(user)
    db.session.commit()
    return user


def test_html_admin_cannot_demote_own_role(client, login_as):
    admin = login_as("ADMIN")

    response = client.patch(f"/users/{admin.id}", data={"role": "OPERATOR"})

    assert_status(response, 200)
    assert "away from Admin" in response.get_data(as_text=True)
    assert get_user(admin.id).role == "ADMIN"


def test_html_admin_can_change_another_admins_role(client, login_as):
    login_as("ADMIN")
    other_admin = _create_user("ADMIN")

    response = client.patch(f"/users/{other_admin.id}", data={"role": "OPERATOR"})

    assert_status(response, 200)
    assert get_user(other_admin.id).role == "OPERATOR"


def test_html_admin_can_edit_own_non_role_field(client, login_as):
    admin = login_as("ADMIN")

    response = client.patch(
        f"/users/{admin.id}", data={"display_name": "Renamed Admin"}
    )

    assert_status(response, 200)
    updated = get_user(admin.id)
    assert updated.display_name == "Renamed Admin"
    assert updated.role == "ADMIN"


def test_html_admin_cannot_delete_own_account(client, login_as):
    admin = login_as("ADMIN")

    response = client.delete(f"/users/{admin.id}")

    assert_status(response, 200)
    assert "delete your own account" in response.get_data(as_text=True)
    assert get_user(admin.id) is not None


def test_html_admin_can_delete_another_admin(client, login_as):
    login_as("ADMIN")
    other_admin = _create_user("ADMIN")

    response = client.delete(f"/users/{other_admin.id}")

    assert_status(response, 200)
    assert get_user(other_admin.id) is None


def test_api_admin_cannot_demote_own_role(client, login_as):
    admin = login_as("ADMIN")

    response = client.patch(f"/api/users/{admin.id}/", json={"role": "OPERATOR"})

    assert_status(response, 409)
    assert get_user(admin.id).role == "ADMIN"


def test_api_admin_can_change_another_admins_role(client, login_as):
    login_as("ADMIN")
    other_admin = _create_user("ADMIN")

    response = client.patch(f"/api/users/{other_admin.id}/", json={"role": "OPERATOR"})

    assert_status(response, 200)
    assert response.json["role"] == "OPERATOR"
    assert get_user(other_admin.id).role == "OPERATOR"


def test_api_admin_can_edit_own_non_role_field(client, login_as):
    admin = login_as("ADMIN")

    response = client.patch(
        f"/api/users/{admin.id}/", json={"display_name": "Renamed Admin"}
    )

    assert_status(response, 200)
    assert response.json["display_name"] == "Renamed Admin"
    assert get_user(admin.id).role == "ADMIN"


def test_api_admin_cannot_delete_own_account(client, login_as):
    admin = login_as("ADMIN")

    response = client.delete(f"/api/users/{admin.id}/")

    assert_status(response, 409)
    assert get_user(admin.id) is not None


def test_api_admin_can_delete_another_admin(client, login_as):
    login_as("ADMIN")
    other_admin = _create_user("ADMIN")

    response = client.delete(f"/api/users/{other_admin.id}/")

    assert_status(response, 204)
    assert get_user(other_admin.id) is None


def test_api_update_user_unauthenticated_returns_401(client):
    target = _create_user("OPERATOR")

    response = client.patch(f"/api/users/{target.id}/", json={"display_name": "X"})

    assert_status(response, 401)


def test_api_update_user_non_admin_returns_403(client, login_as):
    login_as("REQUESTER")
    target = _create_user("OPERATOR")

    response = client.patch(f"/api/users/{target.id}/", json={"display_name": "X"})

    assert_status(response, 403)


def test_api_delete_user_unauthenticated_returns_401(client):
    target = _create_user("OPERATOR")

    response = client.delete(f"/api/users/{target.id}/")

    assert_status(response, 401)


def test_api_delete_user_non_admin_returns_403(client, login_as):
    login_as("REQUESTER")
    target = _create_user("OPERATOR")

    response = client.delete(f"/api/users/{target.id}/")

    assert_status(response, 403)
