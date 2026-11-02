from apiflask import APIBlueprint, EmptySchema, abort
from flask_login import current_user

from app.schemas.room import RoomIn, RoomOut
from app.services.audit import log_action
from app.services.auth import role_required
from app.services.room import (
    create_room,
    delete_room,
    get_room,
    list_rooms,
    update_room,
)

rooms_blp = APIBlueprint("rooms", __name__, url_prefix="/api/rooms", tag="Rooms")


@rooms_blp.get("/")
@rooms_blp.output(RoomOut(many=True))
def get_rooms():
    return list_rooms()


@rooms_blp.post("/")
@rooms_blp.input(RoomIn)
@rooms_blp.output(RoomOut, status_code=201)
@role_required("ADMIN")
def create_room_view(json_data):
    try:
        room = create_room(json_data)
        log_action(
            current_user.id if current_user.is_authenticated else None,
            "room.create",
            entity_type="room",
            entity_id=room.id,
            details=room.code,
        )
        return room
    except ValueError as err:
        abort(422, message=str(err))


@rooms_blp.get("/<int:room_id>/")
@rooms_blp.output(RoomOut)
def get_room_view(room_id):
    room = get_room(room_id)
    if room is None:
        abort(404, message="Room not found.")
    return room


@rooms_blp.patch("/<int:room_id>/")
@rooms_blp.input(RoomIn(partial=True))
@rooms_blp.output(RoomOut)
@role_required("ADMIN")
def update_room_view(room_id, json_data):
    room = get_room(room_id)
    if room is None:
        abort(404, message="Room not found.")
    try:
        room = update_room(room, json_data)
        log_action(
            current_user.id if current_user.is_authenticated else None,
            "room.update",
            entity_type="room",
            entity_id=room.id,
            details=room.code,
        )
        return room
    except ValueError as err:
        abort(422, message=str(err))


@rooms_blp.delete("/<int:room_id>/")
@rooms_blp.output(EmptySchema, status_code=204)
@role_required("ADMIN")
def delete_room_view(room_id):
    room = get_room(room_id)
    if room is None:
        abort(404, message="Room not found.")
    room_id = room.id
    code = room.code
    delete_room(room)
    log_action(
        current_user.id if current_user.is_authenticated else None,
        "room.delete",
        entity_type="room",
        entity_id=room_id,
        details=code,
    )
