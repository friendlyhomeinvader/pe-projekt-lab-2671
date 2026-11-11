import itertools
from datetime import datetime, timedelta, timezone

from app import db
from app.models.booking import Booking
from app.models.key import Key
from app.models.room import Room
from app.models.user import User
from app.services.booking import (
    BOOKING_STATE_LABELS,
    BOOKING_STATE_STYLES,
    list_in_progress_and_upcoming_bookings,
)
from app.services.key_transaction import issue_key

_counter = itertools.count()

NOW = datetime.now(timezone.utc).replace(tzinfo=None)


def _create_room(**overrides):
    n = next(_counter)
    defaults = {"code": f"BP{n}", "location": "Building BP", "capacity": 10}
    defaults.update(overrides)
    room = Room(**defaults)
    db.session.add(room)
    db.session.commit()
    return room


def _create_key(room, **overrides):
    n = next(_counter)
    defaults = {"tag": f"BP-KEY-{n}", "is_master_key": False, "room_id": room.id}
    defaults.update(overrides)
    key = Key(**defaults)
    db.session.add(key)
    db.session.commit()
    return key


def _create_user(role, **overrides):
    n = next(_counter)
    defaults = {
        "username": f"bp.{role.lower()}.{n}",
        "display_name": f"BP {role.title()} {n}",
        "email": f"bp.{role.lower()}.{n}@uni.su",
        "role": role,
    }
    defaults.update(overrides)
    user = User(**defaults)
    user.set_password("Password123456!!")
    db.session.add(user)
    db.session.commit()
    return user


def _create_booking(requester, room, start_date, end_date, state="PENDING"):
    booking = Booking(
        start_date=start_date,
        end_date=end_date,
        state=state,
        requester_id=requester.id,
        room_id=room.id,
    )
    db.session.add(booking)
    db.session.commit()
    return booking


def _row_for(booking_id):
    rows = list_in_progress_and_upcoming_bookings()
    matches = [row for row in rows if row["booking"].id == booking_id]
    assert len(matches) == 1
    return matches[0]


def test_pending_booking_past_start_date_still_shows_pending(client):
    requester = _create_user("REQUESTER")
    room = _create_room()
    booking = _create_booking(
        requester, room, NOW - timedelta(hours=1), NOW + timedelta(hours=1)
    )

    row = _row_for(booking.id)

    assert row["state_label"] == "Pending"
    assert row["state_style"] == BOOKING_STATE_STYLES["PENDING"]


def test_booking_with_issued_key_shows_active(client):
    requester = _create_user("REQUESTER")
    operator = _create_user("OPERATOR")
    room = _create_room()
    key = _create_key(room)
    booking = _create_booking(
        requester, room, NOW - timedelta(hours=1), NOW + timedelta(hours=1)
    )

    issue_key(
        key,
        identification_type="PIN",
        identification_value="1234",
        operator_id=operator.id,
        booking_id=booking.id,
    )

    row = _row_for(booking.id)

    assert row["state_label"] == "Active"
    assert row["state_style"] == BOOKING_STATE_STYLES["ACTIVE"]
    assert row["booking"].state == "ACTIVE"


def test_pending_booking_future_start_date_shows_pending(client):
    requester = _create_user("REQUESTER")
    room = _create_room()
    booking = _create_booking(
        requester, room, NOW + timedelta(hours=1), NOW + timedelta(hours=2)
    )

    row = _row_for(booking.id)

    assert row["state_label"] == "Pending"
    assert row["state_style"] == BOOKING_STATE_STYLES["PENDING"]


def test_ordering_is_unchanged_by_the_state_driven_pill_rework(client):
    requester = _create_user("REQUESTER")
    room_a = _create_room()
    room_b = _create_room()
    room_c = _create_room()

    in_progress_soon_to_finish = _create_booking(
        requester, room_a, NOW - timedelta(hours=2), NOW + timedelta(hours=1)
    )
    upcoming_mid = _create_booking(
        requester, room_b, NOW + timedelta(hours=2), NOW + timedelta(hours=5)
    )
    in_progress_later_finish = _create_booking(
        requester, room_c, NOW - timedelta(hours=1), NOW + timedelta(hours=3)
    )

    rows = list_in_progress_and_upcoming_bookings()
    ordered_ids = [row["booking"].id for row in rows]

    assert ordered_ids == [
        in_progress_soon_to_finish.id,
        upcoming_mid.id,
        in_progress_later_finish.id,
    ]


def test_bookings_fragment_renders_active_and_pending_pills(client, login_as):
    login_as("OPERATOR")
    requester = _create_user("REQUESTER")
    operator = _create_user("OPERATOR")
    active_room = _create_room()
    pending_room = _create_room()
    key = _create_key(active_room)

    active_booking = _create_booking(
        requester, active_room, NOW - timedelta(hours=1), NOW + timedelta(hours=1)
    )
    pending_booking = _create_booking(
        requester, pending_room, NOW + timedelta(hours=1), NOW + timedelta(hours=2)
    )

    issue_key(
        key,
        identification_type="PIN",
        identification_value="1234",
        operator_id=operator.id,
        booking_id=active_booking.id,
    )

    response = client.get("/key-handling/bookings", headers={"HX-Request": "true"})

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert BOOKING_STATE_LABELS["ACTIVE"] in body
    assert BOOKING_STATE_LABELS["PENDING"] in body
    assert "In Progress" not in body
    assert "Upcoming" not in body
    assert pending_booking.id is not None


def test_unresolved_active_booking_is_flagged_key_overdue(client, login_as):
    login_as("OPERATOR")
    requester = _create_user("REQUESTER")
    operator = _create_user("OPERATOR")
    room = _create_room()
    key = _create_key(room)
    booking = _create_booking(
        requester, room, NOW - timedelta(hours=3), NOW - timedelta(hours=1)
    )
    issue_key(
        key,
        identification_type="PIN",
        identification_value="1234",
        operator_id=operator.id,
        booking_id=booking.id,
    )

    response = client.get("/key-handling/bookings", headers={"HX-Request": "true"})

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Key overdue" in body
    assert "No-show pending" not in body


def test_unresolved_pending_booking_is_flagged_no_show_pending(client, login_as):
    login_as("OPERATOR")
    requester = _create_user("REQUESTER")
    room = _create_room()
    _create_booking(requester, room, NOW - timedelta(hours=3), NOW - timedelta(hours=1))

    response = client.get("/key-handling/bookings", headers={"HX-Request": "true"})

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "No-show pending" in body
    assert "Key overdue" not in body
