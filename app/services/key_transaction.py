from datetime import datetime, timedelta, timezone

from app import db
from app.models.booking import Booking
from app.models.key import Key
from app.models.key_transaction import KeyTransaction
from app.models.user import USER_IDENTIFICATION_METHODS, User, UserIdentification
from app.services.booking import LIVE_STATES
from app.services.key_authorization import active_assignee_ids_for_key


def key_room_ids(key):
    room_ids = {key.room_id}
    if key.is_master_key:
        room_ids.update(r.id for r in key.rooms)
    return room_ids


def get_open_transaction(key_id):
    return (
        KeyTransaction.query.filter_by(key_id=key_id, state="ISSUED")
        .order_by(KeyTransaction.id.desc())
        .first()
    )


def is_key_out(key_id):
    return get_open_transaction(key_id) is not None


def open_transactions_by_key_id(key_ids):
    if not key_ids:
        return {}
    rows = KeyTransaction.query.filter(
        KeyTransaction.key_id.in_(key_ids), KeyTransaction.state == "ISSUED"
    ).all()
    return {row.key_id: row for row in rows}


def eligible_bookings_for_key(key):
    room_ids = key_room_ids(key)
    open_booking_ids = [
        row.booking_id
        for row in KeyTransaction.query.filter(
            KeyTransaction.state == "ISSUED", KeyTransaction.booking_id.isnot(None)
        ).all()
    ]
    return (
        Booking.query.filter(
            Booking.room_id.in_(room_ids),
            Booking.state.in_(LIVE_STATES),
            ~Booking.id.in_(open_booking_ids),
        )
        .order_by(Booking.start_date)
        .all()
    )


def find_upcoming_booking_within(room_ids, minutes=60):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    horizon = now + timedelta(minutes=minutes)
    return (
        Booking.query.filter(
            Booking.room_id.in_(room_ids),
            Booking.state.in_(LIVE_STATES),
            Booking.start_date > now,
            Booking.start_date <= horizon,
        )
        .order_by(Booking.start_date)
        .first()
    )


def _resolve_user(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        raise ValueError(f"Unknown user id: {user_id}")
    return user


def _resolve_booking_for_key(booking_id, key):
    if not booking_id:
        return None
    booking = db.session.get(Booking, booking_id)
    if booking is None:
        raise ValueError(f"Unknown booking id: {booking_id}")
    if booking.room_id not in key_room_ids(key):
        raise ValueError("That booking's room is not covered by this key.")
    return booking


def candidate_keys_for_booking(booking):
    room_id = booking.room_id
    non_master = Key.query.filter(Key.room_id == room_id, Key.is_master_key.is_(False)).all()
    master_candidates = (
        Key.query.filter(Key.is_master_key.is_(True))
        .filter(db.or_(Key.room_id == room_id, Key.rooms.any(id=room_id)))
        .all()
    )
    authorized_master = [
        k for k in master_candidates
        if booking.requester_id in active_assignee_ids_for_key(k.id)
    ]
    return non_master + authorized_master


def resolve_key_for_booking(booking):
    candidates = candidate_keys_for_booking(booking)
    if not candidates:
        return None
    available = [k for k in candidates if not is_key_out(k.id)]
    pool = available if available else candidates
    return sorted(pool, key=lambda k: (k.is_master_key, k.id))[0]


INELIGIBLE_HOLDER_ROLES = ("AUDITOR",)


def eligible_holders():
    return User.query.filter(~User.role.in_(INELIGIBLE_HOLDER_ROLES)).order_by(User.id).all()


def issue_key(key, *, identification_type, identification_value, operator_id, holder_id=None, booking_id=None):
    if is_key_out(key.id):
        raise ValueError("Key is already issued.")
    if identification_type not in USER_IDENTIFICATION_METHODS:
        raise ValueError(f"Unknown identification type: {identification_type}")
    if not identification_value:
        raise ValueError("Identification value is required.")

    booking = _resolve_booking_for_key(booking_id, key)

    if booking is not None:
        holder = booking.requester
    else:
        if not holder_id:
            raise ValueError("Holder is required.")
        holder = _resolve_user(holder_id)
        if holder.role in INELIGIBLE_HOLDER_ROLES:
            raise ValueError(f"Cannot issue a key to a user with role {holder.role.title()}.")

    identification = UserIdentification(type=identification_type, value=identification_value)
    db.session.add(identification)
    db.session.flush()

    transaction = KeyTransaction(
        key_id=key.id,
        booking_id=booking.id if booking else None,
        holder_id=holder.id,
        operator_id=operator_id,
        identification_id=identification.id,
        state="ISSUED",
        issued_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.session.add(transaction)
    db.session.commit()
    return transaction


def return_key(transaction, *, room_condition_notes=None, damage_reported=False):
    if transaction.state != "ISSUED":
        raise ValueError("Key is not currently issued.")
    transaction.state = "RETURNED"
    transaction.returned_at = datetime.now(timezone.utc).replace(tzinfo=None)
    transaction.room_condition_notes = room_condition_notes or None
    transaction.damage_reported = bool(damage_reported)
    db.session.commit()
    return transaction
