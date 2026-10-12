from app import db
from app.models.room import Room


def list_rooms():
    return Room.query.order_by(Room.id).all()


def get_room(room_id):
    return db.session.get(Room, room_id)


def create_room(data):
    room = Room(
        code=data["code"],
        location=data["location"],
        capacity=data["capacity"],
    )
    db.session.add(room)
    db.session.commit()
    return room


def update_room(room, data):
    for field in ("code", "location", "capacity"):
        if field in data:
            setattr(room, field, data[field])
    db.session.commit()
    return room


def delete_room(room):
    db.session.delete(room)
    db.session.commit()
