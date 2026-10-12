from tests.factories import feature_payload, room_payload
from tests.helpers import assert_status


def _create_feature(client, **overrides):
    response = client.post("/api/features/", json=feature_payload(**overrides))
    assert_status(response, 201)
    return response.json["id"]


def _create_room(client, **overrides):
    response = client.post("/api/rooms/", json=room_payload(**overrides))
    assert_status(response, 201)
    return response.json


def test_create_room_with_feature_ids(client):
    f1 = _create_feature(client, name="Projector")
    f2 = _create_feature(client, name="Whiteboard")

    response = client.post("/api/rooms/", json=room_payload(feature_ids=[f1, f2]))

    assert_status(response, 201)
    assert set(response.json["feature_ids"]) == {f1, f2}


def test_create_room_without_feature_ids(client):
    response = client.post("/api/rooms/", json=room_payload())

    assert_status(response, 201)
    assert response.json["feature_ids"] == []


def test_create_room_with_unknown_feature_id_is_rejected(client):
    response = client.post("/api/rooms/", json=room_payload(feature_ids=[999999]))

    assert_status(response, 422)
    assert "999999" in response.json["message"]


def test_create_room_with_duplicate_feature_id_succeeds(client):
    f1 = _create_feature(client, name="Projector")

    response = client.post("/api/rooms/", json=room_payload(feature_ids=[f1, f1]))

    assert_status(response, 201)
    assert response.json["feature_ids"] == [f1]


def test_patch_feature_ids_replaces_full_set(client):
    f1 = _create_feature(client, name="Projector")
    f2 = _create_feature(client, name="Whiteboard")
    f3 = _create_feature(client, name="Speakers")

    room = _create_room(client, feature_ids=[f1, f2])

    response = client.patch(f"/api/rooms/{room['id']}/", json={"feature_ids": [f3]})

    assert_status(response, 200)
    assert response.json["feature_ids"] == [f3]


def test_patch_without_feature_ids_leaves_associations_untouched(client):
    f1 = _create_feature(client, name="Projector")
    f2 = _create_feature(client, name="Whiteboard")

    room = _create_room(client, feature_ids=[f1, f2])

    response = client.patch(f"/api/rooms/{room['id']}/", json={"code": "B202"})

    assert_status(response, 200)
    assert response.json["code"] == "B202"
    assert set(response.json["feature_ids"]) == {f1, f2}


def test_patch_feature_ids_with_unknown_id_is_rejected(client):
    room = _create_room(client)

    response = client.patch(f"/api/rooms/{room['id']}/", json={"feature_ids": [999999]})

    assert_status(response, 422)
    assert "999999" in response.json["message"]


def test_patch_feature_ids_to_empty_list_clears_associations(client):
    f1 = _create_feature(client, name="Projector")
    f2 = _create_feature(client, name="Whiteboard")

    room = _create_room(client, feature_ids=[f1, f2])

    response = client.patch(f"/api/rooms/{room['id']}/", json={"feature_ids": []})

    assert_status(response, 200)
    assert response.json["feature_ids"] == []
