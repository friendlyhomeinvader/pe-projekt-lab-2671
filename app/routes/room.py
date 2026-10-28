from flask import abort, render_template, request
from flask_login import current_user
from marshmallow import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.schemas.room import RoomIn
from app.services.auth import role_required
from app.services.feature import list_features
from app.services.nav import grouped_visible_nav_items
from app.services.notify import render_toast
from app.services.page import htmx_only, render_page
from app.services.room import (
    create_room,
    delete_room,
    get_room,
    list_rooms,
    update_room,
)


def _render_room_form(*, is_edit, values, errors, room_id=None, status=200):
    kwargs = {
        "is_edit": is_edit,
        "values": values,
        "errors": errors,
        "all_features": list_features(),
    }
    if room_id is not None:
        kwargs["room_id"] = room_id
    html = render_template("partials/rooms/form.html", **kwargs)
    return (html, status) if status != 200 else html


def _room_save_success(room, verb):
    return render_template(
        "partials/rooms/save_success.html", rooms=list_rooms()
    ) + render_toast("success", f"Room {room.code} {verb}.")


def _field_for_room_error(err):
    return "capacity" if "capacity" in str(err).lower() else "feature_ids"


def register_room_routes(app):
    @app.get("/room-management")
    @role_required("ADMIN")
    def room_management_page():
        return render_page(
            "partials/room_management.html",
            nav_groups=grouped_visible_nav_items(current_user.role),
            title="Room Management",
            rooms=list_rooms(),
        )

    @app.get("/rooms")
    @htmx_only
    @role_required("ADMIN")
    def rooms_list():
        return render_template("partials/rooms/list.html", rooms=list_rooms())

    @app.get("/rooms/new")
    @htmx_only
    @role_required("ADMIN")
    def rooms_new():
        return _render_room_form(is_edit=False, values={}, errors={})

    @app.get("/rooms/<int:room_id>/edit")
    @htmx_only
    @role_required("ADMIN")
    def rooms_edit(room_id):
        room = get_room(room_id)
        if room is None:
            abort(404)
        values = {
            "code": room.code,
            "location": room.location,
            "capacity": room.capacity,
            "feature_ids": [f.id for f in room.features],
        }
        return _render_room_form(
            is_edit=True, room_id=room.id, values=values, errors={}
        )

    @app.post("/rooms")
    @role_required("ADMIN")
    def rooms_create():
        form_data = request.form.to_dict()
        form_data["feature_ids"] = [int(v) for v in request.form.getlist("feature_ids")]

        try:
            data = RoomIn().load(form_data)
        except ValidationError as err:
            return _render_room_form(
                is_edit=False, values=form_data, errors=err.messages, status=422
            )

        try:
            room = create_room(data)
        except ValueError as err:
            return _render_room_form(
                is_edit=False,
                values=form_data,
                errors={_field_for_room_error(err): [str(err)]},
                status=422,
            )

        return _room_save_success(room, "created")

    @app.patch("/rooms/<int:room_id>")
    @role_required("ADMIN")
    def rooms_update(room_id):
        room = get_room(room_id)
        if room is None:
            abort(404)

        form_data = request.form.to_dict()
        form_data["feature_ids"] = [int(v) for v in request.form.getlist("feature_ids")]

        try:
            data = RoomIn(partial=True).load(form_data)
        except ValidationError as err:
            return _render_room_form(
                is_edit=True,
                room_id=room_id,
                values=form_data,
                errors=err.messages,
                status=422,
            )

        try:
            room = update_room(room, data)
        except ValueError as err:
            return _render_room_form(
                is_edit=True,
                room_id=room_id,
                values=form_data,
                errors={_field_for_room_error(err): [str(err)]},
                status=422,
            )

        return _room_save_success(room, "updated")

    @app.get("/rooms/<int:room_id>/delete/confirm")
    @htmx_only
    @role_required("ADMIN")
    def rooms_delete_confirm(room_id):
        room = get_room(room_id)
        if room is None:
            abort(404)
        return render_template("partials/rooms/delete_confirm.html", room=room)

    @app.delete("/rooms/<int:room_id>")
    @role_required("ADMIN")
    def rooms_delete(room_id):
        room = get_room(room_id)
        if room is None:
            abort(404)
        code = room.code
        try:
            delete_room(room)
        except SQLAlchemyError:
            db.session.rollback()
            return (
                render_template(
                    "partials/rooms/delete_success.html", rooms=list_rooms()
                )
                + render_toast("error", "Failed to delete room. Please try again."),
                500,
            )
        return render_template(
            "partials/rooms/delete_success.html", rooms=list_rooms()
        ) + render_toast("success", f"Room {code} deleted.")
