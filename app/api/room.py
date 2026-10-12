from apiflask import APIBlueprint, EmptySchema, abort

from app.schemas.room import RoomIn, RoomOut
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
def create_room_view(json_data):
    room = create_room(json_data)
    return room


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
def update_room_view(room_id, json_data):
    room = get_room(room_id)
    if room is None:
        abort(404, message="Room not found.")
    room = update_room(room, json_data)
    return room


@rooms_blp.delete("/<int:room_id>/")
@rooms_blp.output(EmptySchema, status_code=204)
def delete_room_view(room_id):
    room = get_room(room_id)
    if room is None:
        abort(404, message="Room not found.")
    delete_room(room)
