from datetime import datetime, timezone

from app import db
from app.models.booking import Booking
from app.models.room import Room
from app.models.user import User

LIVE_STATES = ("PENDING", "ACTIVE")


def list_bookings():
    return Booking.query.order_by(Booking.id).all()


def get_booking(booking_id):
    return db.session.get(Booking, booking_id)


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


def create_booking(data):
    _resolve_requester(data["requester_id"])
    _resolve_room(data["room_id"])
    _check_dates(data["start_date"], data["end_date"])
    _check_start_in_future(data["start_date"])
    _check_no_overlap(
        data["room_id"], data["start_date"], data["end_date"], data["state"]
    )

    booking = Booking(
        start_date=data["start_date"],
        end_date=data["end_date"],
        state=data["state"],
        requester_id=data["requester_id"],
        room_id=data["room_id"],
    )
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

    for field in ("start_date", "end_date", "state"):
        if field in data:
            setattr(booking, field, data[field])
    if "room_id" in data:
        booking.room_id = data["room_id"]

    db.session.commit()
    return booking


def delete_booking(booking):
    db.session.delete(booking)
    db.session.commit()
