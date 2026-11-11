from datetime import datetime

import pytest

from app import db
from app.models.booking import Booking
from app.models.room import Room
from app.models.user import User
from app.services.booking import cancel_booking, get_booking
from app.services.maintenance import create_maintenance_slot
from tests.factories import booking_payload
from tests.helpers import assert_status


def _create_booking(client, **overrides):
    response = client.post("/api/bookings/", json=booking_payload(**overrides))
    assert_status(response, 201)
    return response.json


def _create_room_for_maintenance(**overrides):
    defaults = {"code": "MAINT1", "location": "Building M", "capacity": 10}
    defaults.update(overrides)
    room = Room(**defaults)
    db.session.add(room)
    db.session.commit()
    return room


def _create_maintenance_admin():
    user = User(
        username="booking.maintenance.admin",
        display_name="Booking Maintenance Admin",
        email="booking.maintenance.admin@uni.su",
        role="ADMIN",
    )
    user.set_password("Password123456!!")
    db.session.add(user)
    db.session.commit()
    return user


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


def test_create_with_unknown_requester_id_returns_422(client, login_as):
    login_as("REQUESTER")
    response = client.post("/api/bookings/", json=booking_payload(requester_id=999999))

    assert_status(response, 422)
    assert "999999" in response.json["message"]


def test_create_with_unknown_room_id_returns_422(client, login_as):
    login_as("REQUESTER")
    response = client.post("/api/bookings/", json=booking_payload(room_id=999999))

    assert_status(response, 422)
    assert "999999" in response.json["message"]


def test_patch_requester_id_same_value_returns_422(client, login_as):
    login_as("REQUESTER")
    created = _create_booking(client)

    response = client.patch(
        f"/api/bookings/{created['id']}/",
        json={"requester_id": created["requester_id"]},
    )

    assert_status(response, 422)
    assert "requester_id" in response.json["message"]
    assert "modified" in response.json["message"]


def test_patch_requester_id_different_value_returns_422(client, login_as):
    login_as("REQUESTER")
    created = _create_booking(client)
    other_requester_id = booking_payload()["requester_id"]

    response = client.patch(
        f"/api/bookings/{created['id']}/",
        json={"requester_id": other_requester_id},
    )

    assert_status(response, 422)
    assert "requester_id" in response.json["message"]
    assert "modified" in response.json["message"]


def test_create_with_end_date_before_start_date_returns_422(client, login_as):
    login_as("REQUESTER")
    response = client.post(
        "/api/bookings/",
        json=booking_payload(
            start_date="2027-01-10T09:00:00", end_date="2027-01-01T09:00:00"
        ),
    )

    assert_status(response, 422)


def test_create_with_end_date_equal_start_date_returns_422(client, login_as):
    login_as("REQUESTER")
    response = client.post(
        "/api/bookings/",
        json=booking_payload(
            start_date="2027-01-01T09:00:00", end_date="2027-01-01T09:00:00"
        ),
    )

    assert_status(response, 422)


def test_patch_end_date_before_existing_start_date_returns_422(client, login_as):
    login_as("REQUESTER")
    created = _create_booking(client)

    response = client.patch(
        f"/api/bookings/{created['id']}/",
        json={"end_date": "2026-12-01T00:00:00"},
    )

    assert_status(response, 422)

    get_response = client.get(f"/api/bookings/{created['id']}/")
    assert get_response.json["start_date"] == created["start_date"]
    assert get_response.json["end_date"] == created["end_date"]


def test_patch_start_date_after_existing_end_date_returns_422(client, login_as):
    login_as("REQUESTER")
    created = _create_booking(client)

    response = client.patch(
        f"/api/bookings/{created['id']}/",
        json={"start_date": "2027-04-01T00:00:00"},
    )

    assert_status(response, 422)

    get_response = client.get(f"/api/bookings/{created['id']}/")
    assert get_response.json["start_date"] == created["start_date"]
    assert get_response.json["end_date"] == created["end_date"]


def test_patch_both_dates_to_new_valid_range_returns_200(client, login_as):
    login_as("REQUESTER")
    created = _create_booking(client)

    response = client.patch(
        f"/api/bookings/{created['id']}/",
        json={"start_date": "2027-05-01T09:00:00", "end_date": "2027-06-01T09:00:00"},
    )

    assert_status(response, 200)
    assert response.json["start_date"] == "2027-05-01T09:00:00"
    assert response.json["end_date"] == "2027-06-01T09:00:00"


def test_create_with_start_date_in_past_returns_422(client, login_as):
    login_as("REQUESTER")
    response = client.post(
        "/api/bookings/",
        json=booking_payload(start_date="2020-01-01T09:00:00"),
    )

    assert_status(response, 422)


def test_patch_start_date_to_past_returns_422(client, login_as):
    login_as("REQUESTER")
    created = _create_booking(client)

    response = client.patch(
        f"/api/bookings/{created['id']}/",
        json={"start_date": "2020-01-01T09:00:00"},
    )

    assert_status(response, 422)

    get_response = client.get(f"/api/bookings/{created['id']}/")
    assert get_response.json["start_date"] == created["start_date"]


def test_patch_unrelated_field_on_booking_with_past_start_date_succeeds(
    client, login_as
):
    login_as("REQUESTER")
    booking = _insert_booking_directly(
        start_date="2020-01-01T09:00:00",
        end_date="2020-02-01T09:00:00",
        state="PENDING",
    )

    response = client.patch(f"/api/bookings/{booking.id}/", json={"state": "FINISHED"})

    assert_status(response, 200)
    assert response.json["state"] == "FINISHED"


def test_create_overlapping_booking_same_room_returns_422(client, login_as):
    login_as("REQUESTER")
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


def test_create_overlapping_booking_different_rooms_succeeds(client, login_as):
    login_as("REQUESTER")
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


def test_create_overlapping_with_no_show_booking_succeeds(client, login_as):
    login_as("REQUESTER")
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


def test_create_overlapping_with_finished_booking_succeeds(client, login_as):
    login_as("REQUESTER")
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


def test_create_booking_overlapping_maintenance_slot_returns_422(client, login_as):
    login_as("REQUESTER")
    room = _create_room_for_maintenance()
    admin = _create_maintenance_admin()
    create_maintenance_slot(
        {
            "room_id": room.id,
            "start_date": datetime.fromisoformat("2027-01-01T09:00:00"),
            "end_date": datetime.fromisoformat("2027-01-02T09:00:00"),
            "created_by_id": admin.id,
        }
    )

    response = client.post(
        "/api/bookings/",
        json=booking_payload(
            room_id=room.id,
            start_date="2027-01-01T12:00:00",
            end_date="2027-01-01T13:00:00",
        ),
    )

    assert_status(response, 422)
    assert "maintenance" in response.json["message"]


def test_create_booking_outside_maintenance_window_succeeds(client, login_as):
    login_as("REQUESTER")
    room = _create_room_for_maintenance()
    admin = _create_maintenance_admin()
    create_maintenance_slot(
        {
            "room_id": room.id,
            "start_date": datetime.fromisoformat("2027-01-01T09:00:00"),
            "end_date": datetime.fromisoformat("2027-01-02T09:00:00"),
            "created_by_id": admin.id,
        }
    )

    response = client.post(
        "/api/bookings/",
        json=booking_payload(
            room_id=room.id,
            start_date="2027-02-01T09:00:00",
            end_date="2027-02-01T10:00:00",
        ),
    )

    assert_status(response, 201)


def test_patch_booking_dates_into_maintenance_window_returns_422(client, login_as):
    login_as("REQUESTER")
    room = _create_room_for_maintenance()
    admin = _create_maintenance_admin()
    create_maintenance_slot(
        {
            "room_id": room.id,
            "start_date": datetime.fromisoformat("2027-01-01T09:00:00"),
            "end_date": datetime.fromisoformat("2027-01-02T09:00:00"),
            "created_by_id": admin.id,
        }
    )
    booking = _create_booking(
        client,
        room_id=room.id,
        start_date="2027-02-01T09:00:00",
        end_date="2027-02-01T10:00:00",
    )

    response = client.patch(
        f"/api/bookings/{booking['id']}/",
        json={"start_date": "2027-01-01T12:00:00", "end_date": "2027-01-01T13:00:00"},
    )

    assert_status(response, 422)
    assert "maintenance" in response.json["message"]


def test_create_touching_boundary_bookings_same_room_succeeds(client, login_as):
    login_as("REQUESTER")
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


def test_patch_dates_to_collide_with_other_booking_returns_422(client, login_as):
    login_as("REQUESTER")
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


def test_patch_state_to_live_colliding_with_other_booking_returns_422(client, login_as):
    login_as("REQUESTER")
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


def test_cancel_booking_deletes_pending_booking(client):
    booking = _insert_booking_directly(state="PENDING")

    cancel_booking(booking)

    assert get_booking(booking.id) is None


def test_cancel_booking_raises_on_non_pending_state(client):
    booking = _insert_booking_directly(state="ACTIVE")

    with pytest.raises(ValueError):
        cancel_booking(booking)

    reloaded = get_booking(booking.id)
    assert reloaded is not None
    assert reloaded.state == "ACTIVE"


def test_requester_can_cancel_own_pending_booking(client, login_as):
    requester = login_as("REQUESTER")
    created = _create_booking(client, requester_id=requester.id)

    response = client.delete(f"/bookings/{created['id']}")

    assert_status(response, 200)
    get_response = client.get(f"/api/bookings/{created['id']}/")
    assert_status(get_response, 404)


def test_requester_cannot_cancel_own_active_booking(client, login_as):
    requester = login_as("REQUESTER")
    booking = _insert_booking_directly(requester_id=requester.id, state="ACTIVE")

    response = client.delete(f"/bookings/{booking.id}")

    assert_status(response, 200)
    assert "pending" in response.get_data(as_text=True).lower()
    reloaded = get_booking(booking.id)
    assert reloaded is not None
    assert reloaded.state == "ACTIVE"


def test_requester_cannot_cancel_another_requesters_booking(client, login_as):
    login_as("REQUESTER")
    other_booking = _insert_booking_directly(state="PENDING")

    response = client.delete(f"/bookings/{other_booking.id}")

    assert_status(response, 403)
    reloaded = get_booking(other_booking.id)
    assert reloaded is not None
    assert reloaded.state == "PENDING"


def test_admin_can_cancel_another_requesters_pending_booking(client, login_as):
    login_as("ADMIN")
    other_booking = _insert_booking_directly(state="PENDING")

    response = client.delete(f"/bookings/{other_booking.id}")

    assert_status(response, 200)
    assert get_booking(other_booking.id) is None


def test_admin_bypasses_ownership_but_not_pending_state_rule(client, login_as):
    login_as("ADMIN")
    other_booking = _insert_booking_directly(state="ACTIVE")

    response = client.delete(f"/bookings/{other_booking.id}")

    assert_status(response, 200)
    assert "pending" in response.get_data(as_text=True).lower()
    reloaded = get_booking(other_booking.id)
    assert reloaded is not None
    assert reloaded.state == "ACTIVE"
