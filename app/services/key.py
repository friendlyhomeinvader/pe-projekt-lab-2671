from app import db
from app.models.key import Key
from app.models.room import Room


def list_keys():
    return Key.query.order_by(Key.id).all()


def get_key(key_id):
    return db.session.get(Key, key_id)


def _resolve_room(room_id):
    room = db.session.get(Room, room_id)
    if room is None:
        raise ValueError(f"Unknown room id: {room_id}")
    return room


def _resolve_rooms(room_ids):
    found = Room.query.filter(Room.id.in_(room_ids)).all()
    missing = set(room_ids) - {r.id for r in found}
    if missing:
        raise ValueError(f"Unknown room id(s): {sorted(missing)}")
    return found


def _validate_room_assignment(is_master_key, room_id, room_ids):
    if is_master_key and room_id is not None:
        raise ValueError("A master key cannot be assigned to a single room.")
    if not is_master_key and room_ids:
        raise ValueError("Only a master key can be assigned to multiple rooms.")


def create_key(data):
    is_master_key = data.get("is_master_key", False)
    room_id = data.get("room_id")
    room_ids = data.get("room_ids") or []
    _validate_room_assignment(is_master_key, room_id, room_ids)

    key = Key(
        tag=data["tag"],
        is_master_key=is_master_key,
        room_id=_resolve_room(room_id).id if room_id is not None else None,
    )
    if room_ids:
        key.rooms = _resolve_rooms(room_ids)
    db.session.add(key)
    db.session.commit()
    return key


def update_key(key, data):
    is_master_key = data.get("is_master_key", key.is_master_key)
    room_id = data["room_id"] if "room_id" in data else key.room_id
    room_ids = data["room_ids"] if "room_ids" in data else [r.id for r in key.rooms]
    _validate_room_assignment(is_master_key, room_id, room_ids)

    if "tag" in data:
        key.tag = data["tag"]
    if "is_master_key" in data:
        key.is_master_key = data["is_master_key"]
    if "room_id" in data:
        key.room_id = _resolve_room(room_id).id if room_id is not None else None
    if "room_ids" in data:
        key.rooms = _resolve_rooms(room_ids) if room_ids else []

    db.session.commit()
    return key


def delete_key(key):
    db.session.delete(key)
    db.session.commit()
