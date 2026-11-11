from datetime import datetime, timedelta, timezone

import pytest

from app import db
from app.models.audit_log import AuditLog
from app.models.booking import Booking
from app.models.maintenance_slot import MaintenanceSlot
from app.models.room import Room
from app.models.user import User
from app.services.booking import (
    MAX_MULTIBOOKING_WEEKS,
    create_multibooking,
    multibooking_dates,
)
from tests.helpers import assert_status

BASE_START = datetime(2027, 3, 1, 9, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None)
BASE_END = BASE_START + timedelta(minutes=45)


def _create_room(**overrides):
    defaults = {"code": "MB1", "location": "Building MB", "capacity": 10}
    defaults.update(overrides)
    room = Room(**defaults)
    db.session.add(room)
    db.session.commit()
    return room


def _create_requester(**overrides):
    defaults = {
        "username": "mb.requester",
        "display_name": "MB Requester",
        "email": "mb.requester@uni.su",
        "role": "REQUESTER",
    }
    defaults.update(overrides)
    user = User(**defaults)
    user.set_password("Password123456!!")
    db.session.add(user)
    db.session.commit()
    return user


def _insert_booking(room_id, requester_id, start_date, end_date, state="PENDING"):
    booking = Booking(
        start_date=start_date,
        end_date=end_date,
        state=state,
        requester_id=requester_id,
        room_id=room_id,
    )
    db.session.add(booking)
    db.session.commit()
    return booking


def _booking_data(room_id, requester_id, **overrides):
    payload = {
        "start_date": BASE_START,
        "end_date": BASE_END,
        "state": "PENDING",
        "requester_id": requester_id,
        "room_id": room_id,
    }
    payload.update(overrides)
    return payload


def _slot_form_payload(**overrides):
    row_start_iso = BASE_START.isoformat()
    row_end_iso = (BASE_START + timedelta(hours=1)).isoformat()
    payload = {
        "row_start": row_start_iso,
        "row_end": row_end_iso,
        "gap_start": row_start_iso,
        "gap_end": row_end_iso,
        "week_offset": "0",
        "start": row_start_iso,
        "slots": "1",
    }
    payload.update(overrides)
    return payload


def test_multibooking_dates_computes_weekly_occurrences():
    occurrences = multibooking_dates(BASE_START, BASE_END, 3)

    assert len(occurrences) == 4
    assert occurrences[0] == (BASE_START, BASE_END)
    assert occurrences[3] == (
        BASE_START + timedelta(weeks=3),
        BASE_END + timedelta(weeks=3),
    )


def test_create_multibooking_creates_one_booking_per_week(client):
    requester = _create_requester()
    room = _create_room()

    bookings = create_multibooking(_booking_data(room.id, requester.id), extra_weeks=3)

    assert len(bookings) == 4
    assert Booking.query.filter_by(room_id=room.id).count() == 4
    starts = sorted(b.start_date for b in bookings)
    assert starts[0] == BASE_START
    assert starts[-1] == BASE_START + timedelta(weeks=3)


@pytest.mark.parametrize("extra_weeks", [0, MAX_MULTIBOOKING_WEEKS + 1])
def test_create_multibooking_rejects_out_of_range_extra_weeks(client, extra_weeks):
    requester = _create_requester()
    room = _create_room()

    with pytest.raises(ValueError):
        create_multibooking(_booking_data(room.id, requester.id), extra_weeks)

    assert Booking.query.count() == 0


def test_create_multibooking_max_weeks_allows_fourteen_total(client):
    requester = _create_requester()
    room = _create_room()

    bookings = create_multibooking(
        _booking_data(room.id, requester.id), extra_weeks=MAX_MULTIBOOKING_WEEKS
    )

    assert len(bookings) == 14


def test_create_multibooking_conflict_on_later_week_creates_nothing(client):
    requester = _create_requester()
    room = _create_room()
    conflict_start = BASE_START + timedelta(weeks=8)
    conflicting = _insert_booking(
        room.id, requester.id, conflict_start, conflict_start + timedelta(minutes=45)
    )

    with pytest.raises(ValueError) as exc_info:
        create_multibooking(_booking_data(room.id, requester.id), extra_weeks=12)

    assert f"{conflict_start:%Y-%m-%d}" in str(exc_info.value)
    assert Booking.query.filter_by(room_id=room.id).count() == 1
    assert Booking.query.first().id == conflicting.id


def test_create_multibooking_maintenance_conflict_on_later_week_creates_nothing(
    client,
):
    requester = _create_requester()
    room = _create_room()
    conflict_start = BASE_START + timedelta(weeks=4)
    slot = MaintenanceSlot(
        room_id=room.id,
        start_date=conflict_start,
        end_date=conflict_start + timedelta(hours=1),
    )
    db.session.add(slot)
    db.session.commit()

    with pytest.raises(ValueError):
        create_multibooking(_booking_data(room.id, requester.id), extra_weeks=6)

    assert Booking.query.count() == 0


@pytest.mark.parametrize("state", ["NO_SHOW", "FINISHED"])
def test_create_multibooking_ignores_resolved_booking_on_later_week(client, state):
    requester = _create_requester()
    room = _create_room()
    resolved_start = BASE_START + timedelta(weeks=3)
    _insert_booking(
        room.id,
        requester.id,
        resolved_start,
        resolved_start + timedelta(minutes=45),
        state=state,
    )

    bookings = create_multibooking(_booking_data(room.id, requester.id), extra_weeks=5)

    assert len(bookings) == 6


def test_html_multibooking_unconfirmed_shows_confirm_screen_and_creates_nothing(
    client, login_as
):
    login_as("REQUESTER")
    room = _create_room()

    response = client.post(
        f"/bookings/rooms/{room.id}/slots",
        data=_slot_form_payload(multibooking="on", extra_weeks="3"),
    )

    assert_status(response, 200)
    body = response.get_data(as_text=True)
    assert "Confirm multibooking" in body
    assert "4 slots" in body
    for i in range(4):
        occ_date = BASE_START + timedelta(weeks=i)
        assert f"{occ_date:%Y-%m-%d}" in body
    assert Booking.query.count() == 0


def test_html_multibooking_confirmed_creates_bookings_and_audit_rows(client, login_as):
    requester = login_as("REQUESTER")
    room = _create_room()

    response = client.post(
        f"/bookings/rooms/{room.id}/slots",
        data=_slot_form_payload(
            multibooking="on", extra_weeks="3", confirm_multibooking="1"
        ),
    )

    assert_status(response, 200)
    body = response.get_data(as_text=True)
    assert "4 bookings created" in body
    bookings = Booking.query.filter_by(room_id=room.id).all()
    assert len(bookings) == 4
    assert {b.requester_id for b in bookings} == {requester.id}

    logs = AuditLog.query.filter_by(action="booking.create").all()
    assert len(logs) == 4
    assert {log.entity_id for log in logs} == {b.id for b in bookings}


def test_html_multibooking_confirmed_conflict_creates_nothing(client, login_as):
    login_as("REQUESTER")
    room = _create_room()
    other_requester = _create_requester(username="mb.other", email="mb.other@uni.su")
    conflict_start = BASE_START + timedelta(weeks=2)
    _insert_booking(
        room.id,
        other_requester.id,
        conflict_start,
        conflict_start + timedelta(minutes=45),
    )

    response = client.post(
        f"/bookings/rooms/{room.id}/slots",
        data=_slot_form_payload(
            multibooking="on", extra_weeks="3", confirm_multibooking="1"
        ),
    )

    assert_status(response, 422)
    assert f"{conflict_start:%Y-%m-%d}" in response.get_data(as_text=True)
    assert Booking.query.filter_by(room_id=room.id).count() == 1


def test_html_single_booking_path_unaffected_by_multibooking_fields(client, login_as):
    login_as("REQUESTER")
    room = _create_room()

    response = client.post(
        f"/bookings/rooms/{room.id}/slots", data=_slot_form_payload()
    )

    assert_status(response, 200)
    assert "Booking created" in response.get_data(as_text=True)
    assert Booking.query.filter_by(room_id=room.id).count() == 1
