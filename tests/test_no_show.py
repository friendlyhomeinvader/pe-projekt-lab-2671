import itertools
from datetime import datetime, timedelta, timezone

import pytest

from app import db
from app.models.audit_log import AuditLog
from app.models.booking import Booking
from app.models.key_transaction import KeyTransaction
from app.models.room import Room
from app.models.user import User
from app.services.no_show import apply_no_shows
from app.services.preferences import DEFAULT_NO_SHOW_GRACE_MINUTES

_counter = itertools.count()

NOW = datetime.now(timezone.utc).replace(tzinfo=None)
NO_SHOW_GRACE = timedelta(minutes=DEFAULT_NO_SHOW_GRACE_MINUTES)


def _create_user(**overrides):
    n = next(_counter)
    defaults = {
        "username": f"ns.user.{n}",
        "display_name": f"NS User {n}",
        "email": f"ns.user.{n}@uni.su",
        "role": "REQUESTER",
    }
    defaults.update(overrides)
    user = User(**defaults)
    user.set_password("Password123456!!")
    db.session.add(user)
    db.session.commit()
    return user


def _create_room(**overrides):
    n = next(_counter)
    defaults = {"code": f"NS{n}", "location": "Building NS", "capacity": 10}
    defaults.update(overrides)
    room = Room(**defaults)
    db.session.add(room)
    db.session.commit()
    return room


def _create_key(room, **overrides):
    n = next(_counter)
    from app.models.key import Key

    defaults = {"tag": f"NS-KEY-{n}", "is_master_key": False, "room_id": room.id}
    defaults.update(overrides)
    key = Key(**defaults)
    db.session.add(key)
    db.session.commit()
    return key


def _create_booking(**overrides):
    requester = overrides.pop("requester", None) or _create_user()
    room = overrides.pop("room", None) or _create_room()
    defaults = {
        "start_date": NOW - timedelta(hours=1),
        "end_date": NOW + timedelta(hours=1),
        "state": "PENDING",
        "requester_id": requester.id,
        "room_id": room.id,
    }
    defaults.update(overrides)
    booking = Booking(**defaults)
    db.session.add(booking)
    db.session.commit()
    return booking


def _create_transaction(booking, *, state="ISSUED", key=None, holder=None):
    key = key or _create_key(_create_room())
    holder = holder or _create_user()
    transaction = KeyTransaction(
        key_id=key.id,
        booking_id=booking.id,
        holder_id=holder.id,
        operator_id=holder.id,
        state=state,
        issued_at=NOW,
    )
    db.session.add(transaction)
    db.session.commit()
    return transaction


def test_pending_booking_past_grace_without_key_transitions_to_no_show(client):
    booking = _create_booking(
        state="PENDING", start_date=NOW - NO_SHOW_GRACE - timedelta(minutes=1)
    )

    changed = apply_no_shows(now=NOW)

    assert [b.id for b in changed] == [booking.id]
    assert booking.state == "NO_SHOW"


def test_pending_booking_within_grace_stays_pending(client):
    booking = _create_booking(
        state="PENDING", start_date=NOW - NO_SHOW_GRACE + timedelta(minutes=1)
    )

    changed = apply_no_shows(now=NOW)

    assert changed == []
    assert booking.state == "PENDING"


@pytest.mark.parametrize("state", ["PENDING", "ACTIVE"])
def test_booking_with_issued_transaction_stays_live(client, state):
    booking = _create_booking(
        state=state, start_date=NOW - NO_SHOW_GRACE - timedelta(minutes=1)
    )
    _create_transaction(booking, state="ISSUED")

    changed = apply_no_shows(now=NOW)

    assert changed == []
    assert booking.state == state


def test_booking_with_returned_transaction_still_transitions_to_no_show(client):
    booking = _create_booking(
        state="PENDING", start_date=NOW - NO_SHOW_GRACE - timedelta(minutes=1)
    )
    _create_transaction(booking, state="RETURNED")

    changed = apply_no_shows(now=NOW)

    assert [b.id for b in changed] == [booking.id]
    assert booking.state == "NO_SHOW"


@pytest.mark.parametrize("state", ["NO_SHOW", "FINISHED"])
def test_already_resolved_booking_left_alone(client, state):
    booking = _create_booking(
        state=state, start_date=NOW - NO_SHOW_GRACE - timedelta(minutes=1)
    )

    changed = apply_no_shows(now=NOW)

    assert changed == []
    assert booking.state == state


def test_apply_no_shows_is_idempotent_on_second_call(client):
    booking = _create_booking(
        state="PENDING", start_date=NOW - NO_SHOW_GRACE - timedelta(minutes=1)
    )

    first = apply_no_shows(now=NOW)
    second = apply_no_shows(now=NOW)

    assert [b.id for b in first] == [booking.id]
    assert second == []
    assert booking.state == "NO_SHOW"
    assert (
        AuditLog.query.filter_by(entity_type="booking", entity_id=booking.id).count()
        == 1
    )


def test_audit_log_written_only_for_transitioned_bookings(client):
    flagged = _create_booking(
        state="PENDING", start_date=NOW - NO_SHOW_GRACE - timedelta(minutes=1)
    )
    untouched = _create_booking(
        state="PENDING", start_date=NOW - NO_SHOW_GRACE + timedelta(minutes=1)
    )

    apply_no_shows(now=NOW)

    flagged_entries = AuditLog.query.filter_by(
        action="booking.no_show", entity_type="booking", entity_id=flagged.id
    ).all()
    assert len(flagged_entries) == 1
    assert flagged_entries[0].actor_id is None

    untouched_entries = AuditLog.query.filter_by(
        entity_type="booking", entity_id=untouched.id
    ).all()
    assert untouched_entries == []


def test_returned_list_contains_exactly_the_transitioned_bookings(client):
    overdue_no_key = _create_booking(
        state="PENDING", start_date=NOW - NO_SHOW_GRACE - timedelta(minutes=1)
    )
    overdue_with_key = _create_booking(
        state="ACTIVE", start_date=NOW - NO_SHOW_GRACE - timedelta(minutes=1)
    )
    _create_transaction(overdue_with_key, state="ISSUED")
    not_overdue = _create_booking(
        state="PENDING", start_date=NOW - NO_SHOW_GRACE + timedelta(minutes=1)
    )

    changed = apply_no_shows(now=NOW)

    assert {b.id for b in changed} == {overdue_no_key.id}
    assert overdue_with_key.state == "ACTIVE"
    assert not_overdue.state == "PENDING"
