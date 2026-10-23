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


def _validate_additional_rooms(is_master_key, room_ids):
    if not is_master_key and room_ids:
        raise ValueError("Only a master key can have additional rooms.")


def _validate_unique_tag(tag, exclude_id=None):
    existing = Key.query.filter_by(tag=tag).first()
    if existing is not None and existing.id != exclude_id:
        raise ValueError(f"Tag '{tag}' is already in use.")


def create_key(data):
    _validate_unique_tag(data["tag"])
    is_master_key = data.get("is_master_key", False)
    room_ids = data.get("room_ids") or []
    _validate_additional_rooms(is_master_key, room_ids)

    key = Key(
        tag=data["tag"],
        is_master_key=is_master_key,
        room_id=_resolve_room(data["room_id"]).id,
    )
    if room_ids:
        key.rooms = _resolve_rooms(room_ids)
    db.session.add(key)
    db.session.commit()
    return key


def update_key(key, data):
    if "is_master_key" in data:
        raise ValueError("is_master_key cannot be modified after creation.")

    if "tag" in data:
        _validate_unique_tag(data["tag"], exclude_id=key.id)

    room_ids = data["room_ids"] if "room_ids" in data else [r.id for r in key.rooms]
    _validate_additional_rooms(key.is_master_key, room_ids)

    if "tag" in data:
        key.tag = data["tag"]
    if "room_id" in data:
        key.room_id = _resolve_room(data["room_id"]).id
    if "room_ids" in data:
        key.rooms = _resolve_rooms(room_ids) if room_ids else []

    db.session.commit()
    return key


def delete_key(key):
    db.session.delete(key)
    db.session.commit()
