from flask import abort, render_template, request
from flask_login import current_user
from marshmallow import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.schemas.key import KeyIn
from app.services.auth import role_required
from app.services.key import create_key, delete_key, get_key, list_keys, update_key
from app.services.key_authorization import (
    active_assignee_ids_for_key,
    diff_authorized_assignees,
    list_master_keys_with_active_authorizations,
    sync_key_authorizations,
)
from app.services.nav import grouped_visible_nav_items
from app.services.notify import render_toast
from app.services.page import htmx_only, render_page
from app.services.room import list_rooms
from app.services.user import list_users


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
    if message.startswith("is_master_key cannot be modified"):
        return "is_master_key"
    if "already in use" in message:
        return "tag"
    return "_general"


def register_key_routes(app):
    @app.get("/key-management")
    @role_required("ADMIN")
    def key_management_page():
        return render_page(
            "partials/key_management.html",
            nav_groups=grouped_visible_nav_items(current_user.role),
            title="Key Management",
            keys=list_keys(),
        )

    @app.get("/keys")
    @htmx_only
    @role_required("ADMIN")
    def keys_list():
        return render_template("partials/keys/list.html", keys=list_keys())

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
            "room_ids": (
                sorted([key.room_id] + [r.id for r in key.rooms])
                if key.is_master_key
                else []
            ),
        }
        return _render_key_form(
            is_edit=True, key_id=key.id, values=values, errors={}
        )

    @app.post("/keys")
    @role_required("ADMIN")
    def keys_create():
        is_master_key = "is_master_key" in request.form
        submitted_room_ids = sorted(int(v) for v in request.form.getlist("room_ids"))

        if is_master_key and not submitted_room_ids:
            return _render_key_form(
                is_edit=False,
                values={
                    "tag": request.form.get("tag", ""),
                    "is_master_key": True,
                    "room_ids": [],
                },
                errors={"room_ids": ["Select at least one room."]},
                status=422,
            )

        if is_master_key:
            room_id = submitted_room_ids[0]
            extra_room_ids = submitted_room_ids[1:]
        else:
            room_id_raw = request.form.get("room_id", "")
            room_id = int(room_id_raw) if room_id_raw else None
            extra_room_ids = []

        form_data = request.form.to_dict()
        form_data["is_master_key"] = is_master_key
        form_data["room_id"] = room_id
        form_data["room_ids"] = extra_room_ids
        display_values = {**form_data, "room_ids": submitted_room_ids}

        try:
            data = KeyIn().load(form_data)
        except ValidationError as err:
            return _render_key_form(
                is_edit=False, values=display_values, errors=err.messages, status=422
            )

        try:
            key = create_key(data)
        except ValueError as err:
            return _render_key_form(
                is_edit=False,
                values=display_values,
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

        is_master_key = key.is_master_key
        submitted_room_ids = sorted(int(v) for v in request.form.getlist("room_ids"))

        if is_master_key and not submitted_room_ids:
            return _render_key_form(
                is_edit=True,
                key_id=key_id,
                values={
                    "tag": request.form.get("tag", key.tag),
                    "is_master_key": True,
                    "room_ids": [],
                },
                errors={"room_ids": ["Select at least one room."]},
                status=422,
            )

        if is_master_key:
            room_id = submitted_room_ids[0]
            extra_room_ids = submitted_room_ids[1:]
        else:
            room_id_raw = request.form.get("room_id", "")
            room_id = int(room_id_raw) if room_id_raw else None
            extra_room_ids = []

        form_data = request.form.to_dict()
        form_data["room_id"] = room_id
        form_data["room_ids"] = extra_room_ids
        display_values = {
            **form_data,
            "is_master_key": is_master_key,
            "room_ids": submitted_room_ids,
        }

        try:
            data = KeyIn(partial=True).load(form_data)
        except ValidationError as err:
            return _render_key_form(
                is_edit=True,
                key_id=key_id,
                values=display_values,
                errors=err.messages,
                status=422,
            )

        try:
            key = update_key(key, data)
        except ValueError as err:
            return _render_key_form(
                is_edit=True,
                key_id=key_id,
                values=display_values,
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

    @app.get("/key-authorizations")
    @htmx_only
    @role_required("ADMIN")
    def key_authorizations_list():
        return render_template(
            "partials/keys/authorizations_list.html",
            overview=list_master_keys_with_active_authorizations(),
        )

    @app.get("/keys/<int:key_id>/authorizations/edit")
    @htmx_only
    @role_required("ADMIN")
    def keys_authorizations_edit(key_id):
        key = get_key(key_id)
        if key is None or not key.is_master_key:
            abort(404)
        return render_template(
            "partials/keys/authorization_form.html",
            key=key,
            all_users=list_users(),
            active_assignee_ids=active_assignee_ids_for_key(key_id),
        )

    @app.post("/keys/<int:key_id>/authorizations/review")
    @role_required("ADMIN")
    def keys_authorizations_review(key_id):
        key = get_key(key_id)
        if key is None or not key.is_master_key:
            abort(404)

        assignee_ids = sorted(int(v) for v in request.form.getlist("assignee_ids"))
        to_grant_ids, to_revoke_ids = diff_authorized_assignees(key_id, assignee_ids)
        users_by_id = {u.id: u for u in list_users()}
        to_grant = [users_by_id[uid] for uid in to_grant_ids if uid in users_by_id]
        to_revoke = [users_by_id[uid] for uid in to_revoke_ids if uid in users_by_id]

        return (
            render_template(
                "partials/keys/authorization_review.html",
                key=key,
                assignee_ids=assignee_ids,
                to_grant=to_grant,
                to_revoke=to_revoke,
            )
            + render_template("partials/_close_modal.html")
            + render_template("partials/_open_confirm.html")
        )

    @app.post("/keys/<int:key_id>/authorizations")
    @role_required("ADMIN")
    def keys_authorizations_update(key_id):
        key = get_key(key_id)
        if key is None or not key.is_master_key:
            abort(404)

        assignee_ids = [int(v) for v in request.form.getlist("assignee_ids")]

        try:
            granted, revoked = sync_key_authorizations(key, current_user.id, assignee_ids)
        except ValueError as err:
            return (
                render_template(
                    "partials/keys/authorizations_list.html",
                    overview=list_master_keys_with_active_authorizations(),
                )
                + render_template("partials/_close_confirm.html")
                + render_toast("error", str(err)),
                422,
            )

        return render_template(
            "partials/keys/authorizations_list.html",
            overview=list_master_keys_with_active_authorizations(),
        ) + render_template("partials/_close_confirm.html") + render_toast(
            "success", f"Access to {key.tag} updated: {len(granted)} granted, {len(revoked)} revoked."
        )
