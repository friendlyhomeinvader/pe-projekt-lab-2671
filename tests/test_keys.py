from app import db
from app.models.room import Room
from tests.factories import key_payload
from tests.helpers import assert_status


def _create_room(code):
    room = Room(code=code, location="Building K", capacity=10)
    db.session.add(room)
    db.session.commit()
    return room.id


def _create_key(client, **overrides):
    response = client.post("/api/keys/", json=key_payload(**overrides))
    assert_status(response, 201)
    return response.json


def test_create_regular_key_with_room_id(client):
    room_id = _create_room("RK1")

    response = client.post("/api/keys/", json=key_payload(room_id=room_id, room_ids=[]))

    assert_status(response, 201)
    assert response.json["room_id"] == room_id
    assert response.json["room_ids"] == []


def test_create_regular_key_without_room(client):
    response = client.post("/api/keys/", json=key_payload(room_id=None, room_ids=[]))

    assert_status(response, 201)
    assert response.json["room_id"] is None
    assert response.json["room_ids"] == []


def test_create_master_key_with_room_ids(client):
    r1 = _create_room("RK2")
    r2 = _create_room("RK3")

    response = client.post(
        "/api/keys/",
        json=key_payload(is_master_key=True, room_id=None, room_ids=[r1, r2]),
    )

    assert_status(response, 201)
    assert response.json["room_id"] is None
    assert set(response.json["room_ids"]) == {r1, r2}


def test_create_master_key_with_duplicate_room_id_succeeds(client):
    r1 = _create_room("RK4")

    response = client.post(
        "/api/keys/",
        json=key_payload(is_master_key=True, room_id=None, room_ids=[r1, r1]),
    )

    assert_status(response, 201)
    assert response.json["room_ids"] == [r1]


def test_create_regular_key_with_room_ids_is_rejected(client):
    r1 = _create_room("RK5")

    response = client.post(
        "/api/keys/",
        json=key_payload(is_master_key=False, room_id=None, room_ids=[r1]),
    )

    assert_status(response, 422)
    assert "master key" in response.json["message"].lower()


def test_create_master_key_with_room_id_is_rejected(client):
    room_id = _create_room("RK6")

    response = client.post(
        "/api/keys/",
        json=key_payload(is_master_key=True, room_id=room_id, room_ids=[]),
    )

    assert_status(response, 422)
    assert "single room" in response.json["message"].lower()


def test_create_with_unknown_room_id_returns_422(client):
    response = client.post("/api/keys/", json=key_payload(room_id=999999, room_ids=[]))

    assert_status(response, 422)
    assert "999999" in response.json["message"]


def test_create_master_key_with_unknown_room_ids_returns_422(client):
    response = client.post(
        "/api/keys/",
        json=key_payload(is_master_key=True, room_id=None, room_ids=[999999]),
    )

    assert_status(response, 422)
    assert "999999" in response.json["message"]


def test_patch_room_ids_replaces_full_set(client):
    r1 = _create_room("RK7")
    r2 = _create_room("RK8")
    r3 = _create_room("RK9")
    key = _create_key(client, is_master_key=True, room_id=None, room_ids=[r1, r2])

    response = client.patch(f"/api/keys/{key['id']}/", json={"room_ids": [r3]})

    assert_status(response, 200)
    assert response.json["room_ids"] == [r3]


def test_patch_without_room_ids_leaves_associations_untouched(client):
    r1 = _create_room("RK10")
    r2 = _create_room("RK11")
    key = _create_key(client, is_master_key=True, room_id=None, room_ids=[r1, r2])

    response = client.patch(f"/api/keys/{key['id']}/", json={"tag": "RELABELED"})

    assert_status(response, 200)
    assert response.json["tag"] == "RELABELED"
    assert set(response.json["room_ids"]) == {r1, r2}


def test_patch_room_ids_to_empty_list_clears_associations(client):
    r1 = _create_room("RK12")
    key = _create_key(client, is_master_key=True, room_id=None, room_ids=[r1])

    response = client.patch(f"/api/keys/{key['id']}/", json={"room_ids": []})

    assert_status(response, 200)
    assert response.json["room_ids"] == []


def test_patch_room_ids_with_unknown_id_is_rejected(client):
    r1 = _create_room("RK13")
    key = _create_key(client, is_master_key=True, room_id=None, room_ids=[r1])

    response = client.patch(f"/api/keys/{key['id']}/", json={"room_ids": [999999]})

    assert_status(response, 422)
    assert "999999" in response.json["message"]

    get_response = client.get(f"/api/keys/{key['id']}/")
    assert get_response.json["room_ids"] == [r1]


def test_patch_demote_master_key_without_clearing_room_ids_is_rejected(client):
    r1 = _create_room("RK14")
    r2 = _create_room("RK15")
    key = _create_key(client, is_master_key=True, room_id=None, room_ids=[r1, r2])

    response = client.patch(f"/api/keys/{key['id']}/", json={"is_master_key": False})

    assert_status(response, 422)

    get_response = client.get(f"/api/keys/{key['id']}/")
    assert get_response.json["is_master_key"] is True
    assert set(get_response.json["room_ids"]) == {r1, r2}


def test_patch_demote_master_key_clearing_room_ids_succeeds(client):
    r1 = _create_room("RK16")
    r2 = _create_room("RK17")
    key = _create_key(client, is_master_key=True, room_id=None, room_ids=[r1, r2])

    response = client.patch(
        f"/api/keys/{key['id']}/",
        json={"is_master_key": False, "room_ids": [], "room_id": r1},
    )

    assert_status(response, 200)
    assert response.json["is_master_key"] is False
    assert response.json["room_id"] == r1
    assert response.json["room_ids"] == []


def test_patch_promote_regular_key_without_clearing_room_id_is_rejected(client):
    room_id = _create_room("RK18")
    key = _create_key(client, is_master_key=False, room_id=room_id, room_ids=[])

    response = client.patch(f"/api/keys/{key['id']}/", json={"is_master_key": True})

    assert_status(response, 422)

    get_response = client.get(f"/api/keys/{key['id']}/")
    assert get_response.json["is_master_key"] is False
    assert get_response.json["room_id"] == room_id


def test_patch_promote_regular_key_clearing_room_id_succeeds(client):
    room_id = _create_room("RK19")
    r2 = _create_room("RK20")
    key = _create_key(client, is_master_key=False, room_id=room_id, room_ids=[])

    response = client.patch(
        f"/api/keys/{key['id']}/",
        json={"is_master_key": True, "room_id": None, "room_ids": [r2]},
    )

    assert_status(response, 200)
    assert response.json["is_master_key"] is True
    assert response.json["room_id"] is None
    assert response.json["room_ids"] == [r2]
