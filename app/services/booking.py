from datetime import datetime, timedelta, timezone

from app import db
from app.models.booking import Booking
from app.models.maintenance_slot import MaintenanceSlot
from app.models.room import Feature, Room
from app.models.user import User

LIVE_STATES = ("PENDING", "ACTIVE")

MAX_MULTIBOOKING_WEEKS = 13

BOOKING_STATE_LABELS = {
    "PENDING": "Pending",
    "ACTIVE": "Active",
    "NO_SHOW": "No-show",
    "FINISHED": "Finished",
}

BOOKING_STATE_STYLES = {
    "PENDING": "bg-amber-100 border border-amber-300 text-amber-700",
    "ACTIVE": "bg-green-100 border border-green-300 text-green-700",
    "NO_SHOW": "bg-red-100 border border-red-300 text-red-700",
    "FINISHED": "bg-gray-100 border border-gray-300 text-gray-600",
}


def list_bookings():
    return Booking.query.order_by(Booking.id).all()


def get_booking(booking_id):
    return db.session.get(Booking, booking_id)


def list_bookings_for_room(room_id, range_start, range_end):
    return (
        Booking.query.filter(
            Booking.room_id == room_id,
            Booking.start_date < range_end,
            range_start < Booking.end_date,
        )
        .order_by(Booking.start_date)
        .all()
    )


def _resolve_requester(requester_id):
    requester = db.session.get(User, requester_id)
    if requester is None:
        raise ValueError(f"Unknown requester id: {requester_id}")
    return requester


def _resolve_room(room_id):
    room = db.session.get(Room, room_id)
    if room is None:
        raise ValueError(f"Unknown room id: {room_id}")
    return room


def _resolve_features(feature_ids):
    found = Feature.query.filter(Feature.id.in_(feature_ids)).all()
    missing = set(feature_ids) - {f.id for f in found}
    if missing:
        raise ValueError(f"Unknown feature id(s): {sorted(missing)}")
    return found


def missing_room_features(booking):
    room_feature_ids = {f.id for f in booking.room.features}
    return [f for f in booking.features if f.id not in room_feature_ids]


def _check_dates(start_date, end_date):
    if end_date <= start_date:
        raise ValueError("end_date must be after start_date.")


def _check_start_in_future(start_date):
    if start_date < datetime.now(timezone.utc).replace(tzinfo=None):
        raise ValueError("start_date cannot be in the past.")


def _check_no_overlap(room_id, start_date, end_date, state, exclude_booking_id=None):
    if state not in LIVE_STATES:
        return
    query = Booking.query.filter(
        Booking.room_id == room_id,
        Booking.state.in_(LIVE_STATES),
        Booking.start_date < end_date,
        start_date < Booking.end_date,
    )
    if exclude_booking_id is not None:
        query = query.filter(Booking.id != exclude_booking_id)
    other = query.first()
    if other is not None:
        raise ValueError(
            f"Booking overlaps with existing booking id {other.id} for room {room_id}."
        )


def _check_no_maintenance_conflict(room_id, start_date, end_date, state):
    if state not in LIVE_STATES:
        return
    slot = MaintenanceSlot.query.filter(
        MaintenanceSlot.room_id == room_id,
        MaintenanceSlot.start_date < end_date,
        start_date < MaintenanceSlot.end_date,
    ).first()
    if slot is not None:
        raise ValueError(
            f"Room {room_id} is under maintenance from {slot.start_date} to {slot.end_date}."
        )


def multibooking_dates(start_date, end_date, extra_weeks):
    return [
        (start_date + timedelta(weeks=i), end_date + timedelta(weeks=i))
        for i in range(extra_weeks + 1)
    ]


def validate_multibooking(data, extra_weeks):
    if not 1 <= extra_weeks <= MAX_MULTIBOOKING_WEEKS:
        raise ValueError(f"extra_weeks must be between 1 and {MAX_MULTIBOOKING_WEEKS}.")
    _resolve_requester(data["requester_id"])
    _resolve_room(data["room_id"])
    if data.get("feature_ids"):
        _resolve_features(data["feature_ids"])

    occurrences = multibooking_dates(data["start_date"], data["end_date"], extra_weeks)
    _check_start_in_future(occurrences[0][0])
    for occ_start, occ_end in occurrences:
        _check_dates(occ_start, occ_end)
        try:
            _check_no_overlap(data["room_id"], occ_start, occ_end, data["state"])
            _check_no_maintenance_conflict(
                data["room_id"], occ_start, occ_end, data["state"]
            )
        except ValueError as err:
            raise ValueError(f"{occ_start:%Y-%m-%d}: {err}") from err
    return occurrences


def create_multibooking(data, extra_weeks):
    occurrences = validate_multibooking(data, extra_weeks)
    features = (
        _resolve_features(data["feature_ids"]) if data.get("feature_ids") else None
    )

    bookings = []
    for occ_start, occ_end in occurrences:
        booking = Booking(
            start_date=occ_start,
            end_date=occ_end,
            state=data["state"],
            requester_id=data["requester_id"],
            room_id=data["room_id"],
        )
        if features:
            booking.features = features
        db.session.add(booking)
        bookings.append(booking)
    db.session.commit()
    return bookings


def create_booking(data):
    _resolve_requester(data["requester_id"])
    _resolve_room(data["room_id"])
    _check_dates(data["start_date"], data["end_date"])
    _check_start_in_future(data["start_date"])
    _check_no_overlap(
        data["room_id"], data["start_date"], data["end_date"], data["state"]
    )
    _check_no_maintenance_conflict(
        data["room_id"], data["start_date"], data["end_date"], data["state"]
    )

    booking = Booking(
        start_date=data["start_date"],
        end_date=data["end_date"],
        state=data["state"],
        requester_id=data["requester_id"],
        room_id=data["room_id"],
    )
    if data.get("feature_ids"):
        booking.features = _resolve_features(data["feature_ids"])
    db.session.add(booking)
    db.session.commit()
    return booking


def update_booking(booking, data):
    if "requester_id" in data:
        raise ValueError("requester_id cannot be modified after creation.")

    if "room_id" in data:
        _resolve_room(data["room_id"])

    effective_start = data.get("start_date", booking.start_date)
    effective_end = data.get("end_date", booking.end_date)
    _check_dates(effective_start, effective_end)

    if "start_date" in data:
        _check_start_in_future(data["start_date"])

    effective_room_id = data.get("room_id", booking.room_id)
    effective_state = data.get("state", booking.state)
    _check_no_overlap(
        effective_room_id,
        effective_start,
        effective_end,
        effective_state,
        exclude_booking_id=booking.id,
    )
    _check_no_maintenance_conflict(
        effective_room_id, effective_start, effective_end, effective_state
    )

    for field in ("start_date", "end_date", "state"):
        if field in data:
            setattr(booking, field, data[field])
    if "room_id" in data:
        booking.room_id = data["room_id"]
    if "feature_ids" in data:
        booking.features = _resolve_features(data["feature_ids"])

    db.session.commit()
    return booking


def delete_booking(booking):
    db.session.delete(booking)
    db.session.commit()


def cancel_booking(booking):
    if booking.state != "PENDING":
        raise ValueError("Only pending bookings can be cancelled.")
    delete_booking(booking)


def list_in_progress_and_upcoming_bookings():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    live = Booking.query.filter(
        Booking.state.in_(LIVE_STATES), Booking.end_date > now
    ).all()
    rows = []
    for booking in live:
        in_progress = booking.start_date <= now
        rows.append(
            {
                "booking": booking,
                "state_label": BOOKING_STATE_LABELS[booking.state],
                "state_style": BOOKING_STATE_STYLES[booking.state],
                "sort_date": booking.end_date if in_progress else booking.start_date,
            }
        )
    rows.sort(key=lambda row: row["sort_date"])
    return rows


def list_unresolved_bookings():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return (
        Booking.query.filter(Booking.state.in_(LIVE_STATES), Booking.end_date <= now)
        .order_by(Booking.end_date)
        .all()
    )
