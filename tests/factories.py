import itertools

from app import db
from app.models.room import Room
from app.models.user import User

_booking_counter = itertools.count()


def user_payload(**overrides):
    payload = {
        "username": "john.doe",
        "display_name": "John Doe",
        "email": "john.doe@uni.su",
        "role": "OPERATOR",
        "password": "Password123456!!",
    }
    payload.update(overrides)
    return payload


def room_payload(**overrides):
    payload = {
        "code": "PC0",
        "location": "Building I",
        "capacity": 30,
    }
    payload.update(overrides)
    return payload


def feature_payload(**overrides):
    payload = {
        "name": "Projector",
        "description": "Ceiling-mounted projector",
    }
    payload.update(overrides)
    return payload


def key_payload(**overrides):
    payload = {
        "tag": f"K-{next(_booking_counter)}",
        "is_master_key": False,
    }
    if "room_id" not in overrides:
        n = next(_booking_counter)
        room = Room(code=f"K{n}", location="Building K", capacity=10)
        db.session.add(room)
        db.session.commit()
        payload["room_id"] = room.id
    payload.update(overrides)
    return payload


def booking_payload(**overrides):
    payload = {
        "start_date": "2027-01-01T09:00:00",
        "end_date": "2027-03-01T10:00:00",
        "state": "PENDING",
    }

    if "requester_id" not in overrides:
        n = next(_booking_counter)
        user = User(
            username=f"booking.requester.{n}",
            display_name=f"Booking Requester {n}",
            email=f"booking.requester.{n}@uni.su",
            role="REQUESTER",
        )
        user.set_password("Password123456!!")
        db.session.add(user)
        db.session.commit()
        payload["requester_id"] = user.id

    if "room_id" not in overrides:
        n = next(_booking_counter)
        room = Room(
            code=f"B{n}",
            location="Building B",
            capacity=10,
        )
        db.session.add(room)
        db.session.commit()
        payload["room_id"] = room.id

    payload.update(overrides)
    return payload
