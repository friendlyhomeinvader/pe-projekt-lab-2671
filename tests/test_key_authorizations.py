import itertools

from app import db
from app.models.user import User
from tests.factories import key_payload, user_payload
from tests.helpers import assert_status

_user_counter = itertools.count()


def _create_room_free_key(client, **overrides):
    response = client.post("/api/keys/", json=key_payload(**overrides))
    assert_status(response, 201)
    return response.json


def _create_master_key(client, **overrides):
    overrides.setdefault("is_master_key", True)
    return _create_room_free_key(client, **overrides)


def _create_regular_key(client, **overrides):
    overrides.setdefault("is_master_key", False)
    return _create_room_free_key(client, **overrides)


def _create_user(**overrides):
    n = next(_user_counter)
    payload = user_payload(
        username=f"authz.user.{n}",
        email=f"authz.user.{n}@uni.su",
        **overrides,
    )
    user = User(
        username=payload["username"],
        display_name=payload["display_name"],
        email=payload["email"],
        role=payload["role"],
    )
    user.set_password(payload["password"])
    db.session.add(user)
    db.session.commit()
    return user.id


def _create_authorization(client, key_id, assignee_id, assigner_id):
    response = client.post(
        "/api/key-authorizations/grant",
        json={"key_id": key_id, "assignee_id": assignee_id, "assigner_id": assigner_id},
    )
    assert_status(response, 201)
    return response.json


def test_grant_against_non_master_key_is_rejected(client):
    key = _create_regular_key(client)
    assignee_id = _create_user()
    assigner_id = _create_user()

    response = client.post(
        "/api/key-authorizations/grant",
        json={"key_id": key["id"], "assignee_id": assignee_id, "assigner_id": assigner_id},
    )

    assert_status(response, 422)
    assert "master key" in response.json["message"].lower()


def test_grant_against_master_key_succeeds(client):
    key = _create_master_key(client)
    assignee_id = _create_user()
    assigner_id = _create_user()

    response = client.post(
        "/api/key-authorizations/grant",
        json={"key_id": key["id"], "assignee_id": assignee_id, "assigner_id": assigner_id},
    )

    assert_status(response, 201)
    assert response.json["key_id"] == key["id"]
    assert response.json["assignee_id"] == assignee_id
    assert response.json["assigner_id"] == assigner_id
    assert response.json["granted_at"] is not None
    assert response.json["revoked_at"] is None


def test_grant_duplicate_active_authorization_is_rejected(client):
    key = _create_master_key(client)
    assignee_id = _create_user()
    assigner_id = _create_user()
    _create_authorization(client, key["id"], assignee_id, assigner_id)

    response = client.post(
        "/api/key-authorizations/grant",
        json={"key_id": key["id"], "assignee_id": assignee_id, "assigner_id": assigner_id},
    )

    assert_status(response, 422)
    message = response.json["message"].lower()
    assert "already" in message
    assert "active" in message


def test_grant_after_revoke_succeeds_with_new_row(client):
    key = _create_master_key(client)
    assignee_id = _create_user()
    assigner_id = _create_user()
    first = _create_authorization(client, key["id"], assignee_id, assigner_id)

    revoke_response = client.post(f"/api/key-authorizations/{first['id']}/revoke")
    assert_status(revoke_response, 200)

    second_response = client.post(
        "/api/key-authorizations/grant",
        json={"key_id": key["id"], "assignee_id": assignee_id, "assigner_id": assigner_id},
    )

    assert_status(second_response, 201)
    assert second_response.json["id"] != first["id"]


def test_revoke_sets_revoked_at(client):
    key = _create_master_key(client)
    assignee_id = _create_user()
    assigner_id = _create_user()
    authorization = _create_authorization(client, key["id"], assignee_id, assigner_id)

    response = client.post(f"/api/key-authorizations/{authorization['id']}/revoke")

    assert_status(response, 200)
    assert response.json["revoked_at"] is not None


def test_revoke_already_revoked_authorization_is_rejected(client):
    key = _create_master_key(client)
    assignee_id = _create_user()
    assigner_id = _create_user()
    authorization = _create_authorization(client, key["id"], assignee_id, assigner_id)
    first_revoke = client.post(f"/api/key-authorizations/{authorization['id']}/revoke")
    assert_status(first_revoke, 200)

    response = client.post(f"/api/key-authorizations/{authorization['id']}/revoke")

    assert_status(response, 422)
    message = response.json["message"].lower()
    assert "already" in message
    assert "revoked" in message


def test_revoke_nonexistent_authorization_returns_404(client):
    response = client.post("/api/key-authorizations/999999/revoke")

    assert_status(response, 404)


def test_get_nonexistent_authorization_returns_404(client):
    response = client.get("/api/key-authorizations/999999/")

    assert_status(response, 404)


def test_list_authorizations_returns_all_created(client):
    key = _create_master_key(client)
    assignee_1 = _create_user()
    assignee_2 = _create_user()
    assigner_id = _create_user()
    first = _create_authorization(client, key["id"], assignee_1, assigner_id)
    second = _create_authorization(client, key["id"], assignee_2, assigner_id)

    response = client.get("/api/key-authorizations/")

    assert_status(response, 200)
    ids = [item["id"] for item in response.json]
    assert ids == sorted(ids)
    assert first["id"] in ids
    assert second["id"] in ids


def test_get_single_authorization_returns_correct_record(client):
    key = _create_master_key(client)
    assignee_id = _create_user()
    assigner_id = _create_user()
    authorization = _create_authorization(client, key["id"], assignee_id, assigner_id)

    response = client.get(f"/api/key-authorizations/{authorization['id']}/")

    assert_status(response, 200)
    assert response.json["id"] == authorization["id"]
    assert response.json["key_id"] == key["id"]
    assert response.json["assignee_id"] == assignee_id
    assert response.json["assigner_id"] == assigner_id


def test_grant_with_unknown_key_id_returns_422(client):
    assignee_id = _create_user()
    assigner_id = _create_user()

    response = client.post(
        "/api/key-authorizations/grant",
        json={"key_id": 999999, "assignee_id": assignee_id, "assigner_id": assigner_id},
    )

    assert_status(response, 422)
    assert "999999" in response.json["message"]


def test_grant_with_unknown_assignee_id_returns_422(client):
    key = _create_master_key(client)
    assigner_id = _create_user()

    response = client.post(
        "/api/key-authorizations/grant",
        json={"key_id": key["id"], "assignee_id": 999999, "assigner_id": assigner_id},
    )

    assert_status(response, 422)
    assert "999999" in response.json["message"]


def test_grant_with_unknown_assigner_id_returns_422(client):
    key = _create_master_key(client)
    assignee_id = _create_user()

    response = client.post(
        "/api/key-authorizations/grant",
        json={"key_id": key["id"], "assignee_id": assignee_id, "assigner_id": 999999},
    )

    assert_status(response, 422)
    assert "999999" in response.json["message"]


def test_grant_with_missing_required_field_returns_422(client):
    key = _create_master_key(client)
    assignee_id = _create_user()

    response = client.post(
        "/api/key-authorizations/grant",
        json={"key_id": key["id"], "assignee_id": assignee_id},
    )

    assert_status(response, 422)
