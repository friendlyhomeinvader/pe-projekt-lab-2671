import itertools
from datetime import datetime, timedelta, timezone

from app import db
from app.models.key import Key
from app.models.key_transaction import KeyTransaction
from app.models.maintenance_slot import MaintenanceSlot
from app.models.room import Room
from app.models.user import User
from app.services.key_transaction import (
    occupied_room_ids,
    open_transactions_by_key_id,
    room_status_for_keys,
)
from app.services.maintenance import rooms_under_maintenance

_counter = itertools.count()

NOW = datetime.now(timezone.utc).replace(tzinfo=None)


def _create_room(**overrides):
    n = next(_counter)
    defaults = {"code": f"KH{n}", "location": "Building KH", "capacity": 10}
    defaults.update(overrides)
    room = Room(**defaults)
    db.session.add(room)
    db.session.commit()
    return room


def _create_key(room, **overrides):
    n = next(_counter)
    defaults = {"tag": f"KH-KEY-{n}", "is_master_key": False, "room_id": room.id}
    defaults.update(overrides)
    key = Key(**defaults)
    db.session.add(key)
    db.session.commit()
    return key


def _create_holder(**overrides):
    n = next(_counter)
    defaults = {
        "username": f"kh.holder.{n}",
        "display_name": f"KH Holder {n}",
        "email": f"kh.holder.{n}@uni.su",
        "role": "REQUESTER",
    }
    defaults.update(overrides)
    user = User(**defaults)
    user.set_password("Password123456!!")
    db.session.add(user)
    db.session.commit()
    return user


def _issue(key, holder, *, operator=None, issued_at=None, state="ISSUED"):
    operator = operator or holder
    transaction = KeyTransaction(
        key_id=key.id,
        holder_id=holder.id,
        operator_id=operator.id,
        state=state,
        issued_at=issued_at or NOW,
    )
    db.session.add(transaction)
    db.session.commit()
    return transaction


def _create_maintenance_slot(room, start_date, end_date, **overrides):
    slot = MaintenanceSlot(
        room_id=room.id, start_date=start_date, end_date=end_date, **overrides
    )
    db.session.add(slot)
    db.session.commit()
    return slot


def test_room_with_current_maintenance_window_is_reported(client):
    room = _create_room()
    _create_maintenance_slot(room, NOW - timedelta(hours=1), NOW + timedelta(hours=1))

    result = rooms_under_maintenance([room.id], now=NOW)

    assert result == {room.id}


def test_room_with_past_maintenance_window_is_not_reported(client):
    room = _create_room()
    _create_maintenance_slot(room, NOW - timedelta(days=2), NOW - timedelta(days=1))

    result = rooms_under_maintenance([room.id], now=NOW)

    assert result == set()


def test_room_with_future_maintenance_window_is_not_reported(client):
    room = _create_room()
    _create_maintenance_slot(room, NOW + timedelta(days=1), NOW + timedelta(days=2))

    result = rooms_under_maintenance([room.id], now=NOW)

    assert result == set()


def test_room_with_open_issued_transaction_is_occupied(client):
    room = _create_room()
    key = _create_key(room)
    holder = _create_holder()
    _issue(key, holder)

    statuses = room_status_for_keys([key])

    assert statuses[room.id]["code"] == "OCCUPIED"
    assert room.id in occupied_room_ids([room.id])


def test_room_with_no_transaction_and_no_maintenance_is_free(client):
    room = _create_room()
    key = _create_key(room)

    statuses = room_status_for_keys([key])

    assert statuses[room.id]["code"] == "FREE"


def test_room_with_current_maintenance_and_no_issued_key_is_under_maintenance(client):
    room = _create_room()
    key = _create_key(room)
    _create_maintenance_slot(room, NOW - timedelta(hours=1), NOW + timedelta(hours=1))

    statuses = room_status_for_keys([key])

    assert statuses[room.id]["code"] == "MAINTENANCE"


def test_room_with_both_occupied_key_and_maintenance_window_prefers_maintenance(
    client,
):
    room = _create_room()
    key = _create_key(room)
    holder = _create_holder()
    _issue(key, holder)
    _create_maintenance_slot(room, NOW - timedelta(hours=1), NOW + timedelta(hours=1))

    statuses = room_status_for_keys([key])

    assert statuses[room.id]["code"] == "MAINTENANCE"


def test_returned_transaction_does_not_count_as_occupied(client):
    room = _create_room()
    key = _create_key(room)
    holder = _create_holder()
    _issue(
        key,
        holder,
        state="RETURNED",
    )

    statuses = room_status_for_keys([key])

    assert statuses[room.id]["code"] == "FREE"
    assert occupied_room_ids([room.id]) == set()


def test_open_transactions_by_key_id_surfaces_holder_and_issued_at(client):
    room = _create_room()
    key = _create_key(room)
    holder = _create_holder(display_name="Jane Holder")
    issued_at = NOW - timedelta(minutes=30)
    transaction = _issue(key, holder, issued_at=issued_at)

    result = open_transactions_by_key_id([key.id])

    assert result[key.id].id == transaction.id
    assert result[key.id].holder.id == holder.id
    assert result[key.id].holder.display_name == "Jane Holder"
    assert result[key.id].issued_at == issued_at


def test_open_transactions_by_key_id_excludes_returned_transactions(client):
    room = _create_room()
    key = _create_key(room)
    holder = _create_holder()
    _issue(key, holder, state="RETURNED")

    result = open_transactions_by_key_id([key.id])

    assert key.id not in result
