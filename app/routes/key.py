from flask import abort, render_template, request
from flask_login import current_user
from marshmallow import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.schemas.key import KeyIn
from app.services.auth import role_required
from app.services.key import create_key, delete_key, get_key, list_keys, update_key
from app.services.nav import grouped_visible_nav_items
from app.services.notify import render_toast
from app.services.page import htmx_only, render_page
from app.services.room import list_rooms


def _render_key_form(*, is_edit, values, errors, key_id=None, status=200):
    kwargs = {
        "is_edit": is_edit,
        "values": values,
        "errors": errors,
        "all_rooms": list_rooms(),
    }
    if key_id is not None:
        kwargs["key_id"] = key_id
    html = render_template("partials/keys/form.html", **kwargs)
    return (html, status) if status != 200 else html


def _key_save_success(key, verb):
    return render_template(
        "partials/keys/save_success.html", keys=list_keys()
    ) + render_toast("success", f"Key {key.tag} {verb}.")


def _field_for_key_error(err):
    message = str(err)
    if message.startswith("Unknown room id(s)"):
        return "room_ids"
    if message.startswith("Unknown room id:"):
        return "room_id"
    return "_general"


def _key_form_data():
    form_data = request.form.to_dict()
    form_data["is_master_key"] = "is_master_key" in request.form
    room_id_raw = form_data.get("room_id", "")
    form_data["room_id"] = int(room_id_raw) if room_id_raw else None
    form_data["room_ids"] = [int(v) for v in request.form.getlist("room_ids")]
    return form_data


def register_key_routes(app):
    @app.get("/key-management")
    @role_required("ADMIN")
    def key_management_page():
        return render_page(
            "partials/keys/list.html",
            nav_groups=grouped_visible_nav_items(current_user.role),
            title="Key Management",
            keys=list_keys(),
        )

    @app.get("/keys/new")
    @htmx_only
    @role_required("ADMIN")
    def keys_new():
        return _render_key_form(is_edit=False, values={}, errors={})

    @app.get("/keys/<int:key_id>/edit")
    @htmx_only
    @role_required("ADMIN")
    def keys_edit(key_id):
        key = get_key(key_id)
        if key is None:
            abort(404)
        values = {
            "tag": key.tag,
            "is_master_key": key.is_master_key,
            "room_id": key.room_id,
            "room_ids": [r.id for r in key.rooms],
        }
        return _render_key_form(
            is_edit=True, key_id=key.id, values=values, errors={}
        )

    @app.post("/keys")
    @role_required("ADMIN")
    def keys_create():
        form_data = _key_form_data()

        try:
            data = KeyIn().load(form_data)
        except ValidationError as err:
            return _render_key_form(
                is_edit=False, values=form_data, errors=err.messages, status=422
            )

        try:
            key = create_key(data)
        except ValueError as err:
            return _render_key_form(
                is_edit=False,
                values=form_data,
                errors={_field_for_key_error(err): [str(err)]},
                status=422,
            )

        return _key_save_success(key, "created")

    @app.patch("/keys/<int:key_id>")
    @role_required("ADMIN")
    def keys_update(key_id):
        key = get_key(key_id)
        if key is None:
            abort(404)

        form_data = _key_form_data()

        try:
            data = KeyIn(partial=True).load(form_data)
        except ValidationError as err:
            return _render_key_form(
                is_edit=True,
                key_id=key_id,
                values=form_data,
                errors=err.messages,
                status=422,
            )

        try:
            key = update_key(key, data)
        except ValueError as err:
            return _render_key_form(
                is_edit=True,
                key_id=key_id,
                values=form_data,
                errors={_field_for_key_error(err): [str(err)]},
                status=422,
            )

        return _key_save_success(key, "updated")

    @app.get("/keys/<int:key_id>/delete/confirm")
    @htmx_only
    @role_required("ADMIN")
    def keys_delete_confirm(key_id):
        key = get_key(key_id)
        if key is None:
            abort(404)
        return render_template("partials/keys/delete_confirm.html", key=key)

    @app.delete("/keys/<int:key_id>")
    @role_required("ADMIN")
    def keys_delete(key_id):
        key = get_key(key_id)
        if key is None:
            abort(404)
        tag = key.tag
        try:
            delete_key(key)
        except SQLAlchemyError:
            db.session.rollback()
            return (
                render_template(
                    "partials/keys/delete_success.html", keys=list_keys()
                )
                + render_toast("error", "Failed to delete key. Please try again."),
                500,
            )
        return render_template(
            "partials/keys/delete_success.html", keys=list_keys()
        ) + render_toast("success", f"Key {tag} deleted.")
