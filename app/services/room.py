from app import db
from app.models.room import Feature, Room


def list_rooms():
    return Room.query.order_by(Room.id).all()


def get_room(room_id):
    return db.session.get(Room, room_id)


def _resolve_features(feature_ids):
    found = Feature.query.filter(Feature.id.in_(feature_ids)).all()
    missing = set(feature_ids) - {f.id for f in found}
    if missing:
        raise ValueError(f"Unknown feature id(s): {sorted(missing)}")
    return found


def create_room(data):
    room = Room(
        code=data["code"],
        location=data["location"],
        capacity=data["capacity"],
    )
    if data.get("feature_ids"):
        room.features = _resolve_features(data["feature_ids"])
    db.session.add(room)
    db.session.commit()
    return room


def update_room(room, data):
    for field in ("code", "location", "capacity"):
        if field in data:
            setattr(room, field, data[field])
    if "feature_ids" in data:
        room.features = _resolve_features(data["feature_ids"])
    db.session.commit()
    return room


def delete_room(room):
    db.session.delete(room)
    db.session.commit()
