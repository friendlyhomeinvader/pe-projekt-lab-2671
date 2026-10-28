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

    response = client.post("/api/keys/", json=key_payload(room_id=room_id))

    assert_status(response, 201)
    assert response.json["room_id"] == room_id
    assert response.json["room_ids"] == []


def test_create_with_duplicate_tag_is_rejected(client):
    r1 = _create_room("RK31")
    r2 = _create_room("RK32")
    _create_key(client, tag="DUPTAG", room_id=r1)

    response = client.post("/api/keys/", json=key_payload(tag="DUPTAG", room_id=r2))

    assert_status(response, 422)
    assert "already in use" in response.json["message"].lower()


def test_patch_tag_to_another_keys_tag_is_rejected(client):
    r1 = _create_room("RK33")
    r2 = _create_room("RK34")
    _create_key(client, tag="TAKEN", room_id=r1)
    other = _create_key(client, tag="FREE", room_id=r2)

    response = client.patch(f"/api/keys/{other['id']}/", json={"tag": "TAKEN"})

    assert_status(response, 422)
    assert "already in use" in response.json["message"].lower()

    get_response = client.get(f"/api/keys/{other['id']}/")
    assert get_response.json["tag"] == "FREE"


def test_patch_tag_to_its_own_current_value_succeeds(client):
    main = _create_room("RK35")
    key = _create_key(client, tag="SAME", room_id=main)

    response = client.patch(f"/api/keys/{key['id']}/", json={"tag": "SAME"})

    assert_status(response, 200)
    assert response.json["tag"] == "SAME"


def test_patch_unrelated_field_does_not_trigger_tag_check(client):
    main = _create_room("RK36")
    other_room = _create_room("RK37")
    key = _create_key(client, tag="UNIQUE-TAG", room_id=main)

    response = client.patch(f"/api/keys/{key['id']}/", json={"room_id": other_room})

    assert_status(response, 200)
    assert response.json["room_id"] == other_room
    assert response.json["tag"] == "UNIQUE-TAG"


def test_create_master_key_with_additional_rooms(client):
    main = _create_room("RK2")
    extra = _create_room("RK3")

    response = client.post(
        "/api/keys/",
        json=key_payload(is_master_key=True, room_id=main, room_ids=[extra]),
    )

    assert_status(response, 201)
    assert response.json["room_id"] == main
    assert response.json["room_ids"] == [extra]


def test_create_master_key_with_duplicate_additional_room_succeeds(client):
    main = _create_room("RK4")
    extra = _create_room("RK5")

    response = client.post(
        "/api/keys/",
        json=key_payload(is_master_key=True, room_id=main, room_ids=[extra, extra]),
    )

    assert_status(response, 201)
    assert response.json["room_ids"] == [extra]


def test_create_regular_key_with_additional_rooms_is_rejected(client):
    main = _create_room("RK6")
    extra = _create_room("RK7")

    response = client.post(
        "/api/keys/",
        json=key_payload(is_master_key=False, room_id=main, room_ids=[extra]),
    )

    assert_status(response, 422)
    assert "master key" in response.json["message"].lower()


def test_create_with_unknown_room_id_returns_422(client):
    response = client.post("/api/keys/", json=key_payload(room_id=999999))

    assert_status(response, 422)
    assert "999999" in response.json["message"]


def test_create_master_key_with_unknown_additional_room_returns_422(client):
    main = _create_room("RK8")

    response = client.post(
        "/api/keys/",
        json=key_payload(is_master_key=True, room_id=main, room_ids=[999999]),
    )

    assert_status(response, 422)
    assert "999999" in response.json["message"]


def test_patch_additional_rooms_replaces_full_set(client):
    main = _create_room("RK9")
    r1 = _create_room("RK10")
    r2 = _create_room("RK11")
    key = _create_key(client, is_master_key=True, room_id=main, room_ids=[r1])

    response = client.patch(f"/api/keys/{key['id']}/", json={"room_ids": [r2]})

    assert_status(response, 200)
    assert response.json["room_ids"] == [r2]


def test_patch_without_additional_rooms_leaves_associations_untouched(client):
    main = _create_room("RK12")
    r1 = _create_room("RK13")
    r2 = _create_room("RK14")
    key = _create_key(client, is_master_key=True, room_id=main, room_ids=[r1, r2])

    response = client.patch(f"/api/keys/{key['id']}/", json={"tag": "RELABELED"})

    assert_status(response, 200)
    assert response.json["tag"] == "RELABELED"
    assert set(response.json["room_ids"]) == {r1, r2}


def test_patch_additional_rooms_to_empty_list_clears_associations(client):
    main = _create_room("RK15")
    r1 = _create_room("RK16")
    key = _create_key(client, is_master_key=True, room_id=main, room_ids=[r1])

    response = client.patch(f"/api/keys/{key['id']}/", json={"room_ids": []})

    assert_status(response, 200)
    assert response.json["room_ids"] == []


def test_patch_additional_rooms_with_unknown_id_is_rejected(client):
    main = _create_room("RK17")
    r1 = _create_room("RK18")
    key = _create_key(client, is_master_key=True, room_id=main, room_ids=[r1])

    response = client.patch(f"/api/keys/{key['id']}/", json={"room_ids": [999999]})

    assert_status(response, 422)
    assert "999999" in response.json["message"]

    get_response = client.get(f"/api/keys/{key['id']}/")
    assert get_response.json["room_ids"] == [r1]


def test_patch_main_room_to_unknown_id_is_rejected(client):
    main = _create_room("RK19")
    key = _create_key(client, room_id=main)

    response = client.patch(f"/api/keys/{key['id']}/", json={"room_id": 999999})

    assert_status(response, 422)
    assert "999999" in response.json["message"]

    get_response = client.get(f"/api/keys/{key['id']}/")
    assert get_response.json["room_id"] == main


def test_patch_is_master_key_to_same_value_is_rejected(client):
    main = _create_room("RK27")
    key = _create_key(client, is_master_key=False, room_id=main)

    response = client.patch(f"/api/keys/{key['id']}/", json={"is_master_key": False})

    assert_status(response, 422)
    assert "modified" in response.json["message"].lower()

    get_response = client.get(f"/api/keys/{key['id']}/")
    assert get_response.json["is_master_key"] is False


def test_patch_is_master_key_to_true_is_rejected(client):
    main = _create_room("RK28")
    key = _create_key(client, is_master_key=False, room_id=main)

    response = client.patch(f"/api/keys/{key['id']}/", json={"is_master_key": True})

    assert_status(response, 422)

    get_response = client.get(f"/api/keys/{key['id']}/")
    assert get_response.json["is_master_key"] is False
    assert get_response.json["room_id"] == main


def test_patch_is_master_key_to_false_on_master_key_is_rejected(client):
    main = _create_room("RK29")
    extra = _create_room("RK30")
    key = _create_key(client, is_master_key=True, room_id=main, room_ids=[extra])

    response = client.patch(f"/api/keys/{key['id']}/", json={"is_master_key": False})

    assert_status(response, 422)

    get_response = client.get(f"/api/keys/{key['id']}/")
    assert get_response.json["is_master_key"] is True
    assert get_response.json["room_ids"] == [extra]
