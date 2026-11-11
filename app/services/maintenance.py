from datetime import datetime, timezone

from app import db
from app.models.maintenance_slot import MaintenanceSlot
from app.models.room import Room
from app.services.booking import LIVE_STATES, list_bookings_for_room


class MaintenanceSlotConflict(ValueError):
    def __init__(self, bookings):
        self.bookings = bookings
        ids = ", ".join(f"#{b.id}" for b in bookings)
        super().__init__(
            f"This slot overlaps {len(bookings)} existing booking(s): {ids}."
        )


def list_maintenance_slots():
    return MaintenanceSlot.query.order_by(MaintenanceSlot.start_date).all()


def get_maintenance_slot(slot_id):
    return db.session.get(MaintenanceSlot, slot_id)


def maintenance_slots_for_room(room_id, range_start, range_end):
    return (
        MaintenanceSlot.query.filter(
            MaintenanceSlot.room_id == room_id,
            MaintenanceSlot.start_date < range_end,
            range_start < MaintenanceSlot.end_date,
        )
        .order_by(MaintenanceSlot.start_date)
        .all()
    )


def conflicting_bookings(room_id, start_date, end_date):
    return [
        b
        for b in list_bookings_for_room(room_id, start_date, end_date)
        if b.state in LIVE_STATES
    ]


def _resolve_room(room_id):
    room = db.session.get(Room, room_id)
    if room is None:
        raise ValueError(f"Unknown room id: {room_id}")
    return room


def _check_dates(start_date, end_date):
    if end_date <= start_date:
        raise ValueError("end_date must be after start_date.")


def _check_no_booking_conflict(room_id, start_date, end_date, confirm_conflicts):
    conflicts = conflicting_bookings(room_id, start_date, end_date)
    if conflicts and not confirm_conflicts:
        raise MaintenanceSlotConflict(conflicts)
    return conflicts


def create_maintenance_slot(data):
    _resolve_room(data["room_id"])
    _check_dates(data["start_date"], data["end_date"])
    conflicts = _check_no_booking_conflict(
        data["room_id"],
        data["start_date"],
        data["end_date"],
        data.get("confirm_conflicts"),
    )

    slot = MaintenanceSlot(
        room_id=data["room_id"],
        start_date=data["start_date"],
        end_date=data["end_date"],
        reason=data.get("reason"),
        created_by_id=data["created_by_id"],
    )
    db.session.add(slot)
    db.session.commit()
    slot.overridden_conflicts = conflicts
    return slot


def update_maintenance_slot(slot, data):
    if "room_id" in data:
        _resolve_room(data["room_id"])

    effective_room_id = data.get("room_id", slot.room_id)
    effective_start = data.get("start_date", slot.start_date)
    effective_end = data.get("end_date", slot.end_date)
    _check_dates(effective_start, effective_end)
    conflicts = _check_no_booking_conflict(
        effective_room_id, effective_start, effective_end, data.get("confirm_conflicts")
    )

    for field in ("room_id", "start_date", "end_date", "reason"):
        if field in data:
            setattr(slot, field, data[field])

    db.session.commit()
    slot.overridden_conflicts = conflicts
    return slot


def delete_maintenance_slot(slot):
    db.session.delete(slot)
    db.session.commit()


def rooms_under_maintenance(room_ids, now=None):
    room_ids = list(room_ids)
    if not room_ids:
        return set()
    if now is None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = MaintenanceSlot.query.filter(
        MaintenanceSlot.room_id.in_(room_ids),
        MaintenanceSlot.start_date <= now,
        MaintenanceSlot.end_date >= now,
    ).all()
    return {row.room_id for row in rows}
