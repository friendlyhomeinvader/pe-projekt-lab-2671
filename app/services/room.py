from app import db
from app.models.room import Feature, Room


def list_rooms(min_capacity=None, feature_ids=None):
    query = Room.query
    if min_capacity is not None:
        query = query.filter(Room.capacity >= min_capacity)
    for feature_id in feature_ids or []:
        query = query.filter(Room.features.any(Feature.id == feature_id))
    return query.order_by(Room.id).all()


def get_room(room_id):
    return db.session.get(Room, room_id)


def _resolve_features(feature_ids):
    found = Feature.query.filter(Feature.id.in_(feature_ids)).all()
    missing = set(feature_ids) - {f.id for f in found}
    if missing:
        raise ValueError(f"Unknown feature id(s): {sorted(missing)}")
    return found


def _validate_capacity(capacity):
    if capacity < 0:
        raise ValueError("Capacity cannot be negative.")


def create_room(data):
    _validate_capacity(data["capacity"])
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
    if "capacity" in data:
        _validate_capacity(data["capacity"])
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
