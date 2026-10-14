from datetime import datetime

from app import db
from app.models.booking import Booking
from tests.factories import booking_payload
from tests.helpers import assert_status


def _create_booking(client, **overrides):
    response = client.post("/api/bookings/", json=booking_payload(**overrides))
    assert_status(response, 201)
    return response.json


def _insert_booking_directly(**overrides):
    payload = booking_payload(**overrides)
    booking = Booking(
        start_date=datetime.fromisoformat(payload["start_date"]),
        end_date=datetime.fromisoformat(payload["end_date"]),
        state=payload["state"],
        requester_id=payload["requester_id"],
        room_id=payload["room_id"],
    )
    db.session.add(booking)
    db.session.commit()
    return booking


def test_create_with_unknown_requester_id_returns_422(client):
    response = client.post("/api/bookings/", json=booking_payload(requester_id=999999))

    assert_status(response, 422)
    assert "999999" in response.json["message"]


def test_create_with_unknown_room_id_returns_422(client):
    response = client.post("/api/bookings/", json=booking_payload(room_id=999999))

    assert_status(response, 422)
    assert "999999" in response.json["message"]


def test_patch_requester_id_same_value_returns_422(client):
    created = _create_booking(client)

    response = client.patch(
        f"/api/bookings/{created['id']}/",
        json={"requester_id": created["requester_id"]},
    )

    assert_status(response, 422)
    assert "requester_id" in response.json["message"]
    assert "modified" in response.json["message"]


def test_patch_requester_id_different_value_returns_422(client):
    created = _create_booking(client)
    other_requester_id = booking_payload()["requester_id"]

    response = client.patch(
        f"/api/bookings/{created['id']}/",
        json={"requester_id": other_requester_id},
    )

    assert_status(response, 422)
    assert "requester_id" in response.json["message"]
    assert "modified" in response.json["message"]


def test_create_with_end_date_before_start_date_returns_422(client):
    response = client.post(
        "/api/bookings/",
        json=booking_payload(
            start_date="2027-01-10T09:00:00", end_date="2027-01-01T09:00:00"
        ),
    )

    assert_status(response, 422)


def test_create_with_end_date_equal_start_date_returns_422(client):
    response = client.post(
        "/api/bookings/",
        json=booking_payload(
            start_date="2027-01-01T09:00:00", end_date="2027-01-01T09:00:00"
        ),
    )

    assert_status(response, 422)


def test_patch_end_date_before_existing_start_date_returns_422(client):
    created = _create_booking(client)

    response = client.patch(
        f"/api/bookings/{created['id']}/",
        json={"end_date": "2026-12-01T00:00:00"},
    )

    assert_status(response, 422)

    get_response = client.get(f"/api/bookings/{created['id']}/")
    assert get_response.json["start_date"] == created["start_date"]
    assert get_response.json["end_date"] == created["end_date"]


def test_patch_start_date_after_existing_end_date_returns_422(client):
    created = _create_booking(client)

    response = client.patch(
        f"/api/bookings/{created['id']}/",
        json={"start_date": "2027-04-01T00:00:00"},
    )

    assert_status(response, 422)

    get_response = client.get(f"/api/bookings/{created['id']}/")
    assert get_response.json["start_date"] == created["start_date"]
    assert get_response.json["end_date"] == created["end_date"]


def test_patch_both_dates_to_new_valid_range_returns_200(client):
    created = _create_booking(client)

    response = client.patch(
        f"/api/bookings/{created['id']}/",
        json={"start_date": "2027-05-01T09:00:00", "end_date": "2027-06-01T09:00:00"},
    )

    assert_status(response, 200)
    assert response.json["start_date"] == "2027-05-01T09:00:00"
    assert response.json["end_date"] == "2027-06-01T09:00:00"


def test_create_with_start_date_in_past_returns_422(client):
    response = client.post(
        "/api/bookings/",
        json=booking_payload(start_date="2020-01-01T09:00:00"),
    )

    assert_status(response, 422)


def test_patch_start_date_to_past_returns_422(client):
    created = _create_booking(client)

    response = client.patch(
        f"/api/bookings/{created['id']}/",
        json={"start_date": "2020-01-01T09:00:00"},
    )

    assert_status(response, 422)

    get_response = client.get(f"/api/bookings/{created['id']}/")
    assert get_response.json["start_date"] == created["start_date"]


def test_patch_unrelated_field_on_booking_with_past_start_date_succeeds(client):
    booking = _insert_booking_directly(
        start_date="2020-01-01T09:00:00",
        end_date="2020-02-01T09:00:00",
        state="PENDING",
    )

    response = client.patch(f"/api/bookings/{booking.id}/", json={"state": "FINISHED"})

    assert_status(response, 200)
    assert response.json["state"] == "FINISHED"


def test_create_overlapping_booking_same_room_returns_422(client):
    first = _create_booking(
        client, start_date="2027-01-01T09:00:00", end_date="2027-02-01T09:00:00"
    )

    response = client.post(
        "/api/bookings/",
        json=booking_payload(
            room_id=first["room_id"],
            start_date="2027-01-15T09:00:00",
            end_date="2027-02-15T09:00:00",
        ),
    )

    assert_status(response, 422)
    assert str(first["id"]) in response.json["message"]


def test_create_overlapping_booking_different_rooms_succeeds(client):
    first = _create_booking(
        client, start_date="2027-01-01T09:00:00", end_date="2027-02-01T09:00:00"
    )

    response = client.post(
        "/api/bookings/",
        json=booking_payload(
            start_date="2027-01-01T09:00:00", end_date="2027-02-01T09:00:00"
        ),
    )

    assert_status(response, 201)
    assert response.json["room_id"] != first["room_id"]


def test_create_overlapping_with_no_show_booking_succeeds(client):
    first = _create_booking(
        client,
        state="NO_SHOW",
        start_date="2027-01-01T09:00:00",
        end_date="2027-02-01T09:00:00",
    )

    response = client.post(
        "/api/bookings/",
        json=booking_payload(
            room_id=first["room_id"],
            start_date="2027-01-01T09:00:00",
            end_date="2027-02-01T09:00:00",
        ),
    )

    assert_status(response, 201)


def test_create_overlapping_with_finished_booking_succeeds(client):
    first = _create_booking(
        client,
        state="FINISHED",
        start_date="2027-01-01T09:00:00",
        end_date="2027-02-01T09:00:00",
    )

    response = client.post(
        "/api/bookings/",
        json=booking_payload(
            room_id=first["room_id"],
            start_date="2027-01-01T09:00:00",
            end_date="2027-02-01T09:00:00",
        ),
    )

    assert_status(response, 201)


def test_create_touching_boundary_bookings_same_room_succeeds(client):
    first = _create_booking(
        client, start_date="2027-01-01T09:00:00", end_date="2027-02-01T09:00:00"
    )

    response = client.post(
        "/api/bookings/",
        json=booking_payload(
            room_id=first["room_id"],
            start_date="2027-02-01T09:00:00",
            end_date="2027-03-01T09:00:00",
        ),
    )

    assert_status(response, 201)


def test_patch_dates_to_collide_with_other_booking_returns_422(client):
    first = _create_booking(
        client, start_date="2027-01-01T09:00:00", end_date="2027-02-01T09:00:00"
    )
    second = _create_booking(
        client,
        room_id=first["room_id"],
        start_date="2027-03-01T09:00:00",
        end_date="2027-04-01T09:00:00",
    )

    response = client.patch(
        f"/api/bookings/{second['id']}/",
        json={"start_date": "2027-01-15T09:00:00", "end_date": "2027-01-20T09:00:00"},
    )

    assert_status(response, 422)
    assert str(first["id"]) in response.json["message"]

    get_response = client.get(f"/api/bookings/{second['id']}/")
    assert get_response.json["start_date"] == second["start_date"]
    assert get_response.json["end_date"] == second["end_date"]


def test_patch_state_to_live_colliding_with_other_booking_returns_422(client):
    first = _create_booking(
        client, start_date="2027-01-01T09:00:00", end_date="2027-02-01T09:00:00"
    )
    second = _create_booking(
        client,
        room_id=first["room_id"],
        state="NO_SHOW",
        start_date="2027-01-15T09:00:00",
        end_date="2027-01-20T09:00:00",
    )

    response = client.patch(f"/api/bookings/{second['id']}/", json={"state": "PENDING"})

    assert_status(response, 422)
    assert str(first["id"]) in response.json["message"]

    get_response = client.get(f"/api/bookings/{second['id']}/")
    assert get_response.json["state"] == "NO_SHOW"
