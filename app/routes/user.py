from flask import abort, render_template, request
from flask_login import current_user
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.user import USER_ROLES
from app.schemas.user import UserIn
from app.services.auth import role_required
from app.services.nav import grouped_visible_nav_items
from app.services.notify import render_toast
from app.services.page import htmx_only, render_page
from app.services.user import (
    create_user,
    delete_user,
    get_user,
    list_users,
    update_user,
)

DUPLICATE_FIELD_ERROR = {"username": ["Username or email already exists."]}


def _render_user_form(*, is_edit, values, errors, user_id=None, status=200):
    kwargs = {
        "is_edit": is_edit,
        "values": values,
        "errors": errors,
        "roles": USER_ROLES,
    }
    if user_id is not None:
        kwargs["user_id"] = user_id
    html = render_template("partials/users/form.html", **kwargs)
    return (html, status) if status != 200 else html


def _save_success(user, verb):
    return render_template(
        "partials/users/save_success.html", users=list_users()
    ) + render_toast("success", f"User {user.username} {verb}.")


def register_user_routes(app):
    @app.get("/user-management")
    @role_required("ADMIN")
    def user_management_page():
        return render_page(
            "partials/users/list.html",
            nav_groups=grouped_visible_nav_items(current_user.role),
            title="User Management",
            users=list_users(),
        )

    @app.get("/users/new")
    @htmx_only
    @role_required("ADMIN")
    def users_new():
        return _render_user_form(is_edit=False, values={}, errors={})

    @app.get("/users/<int:user_id>/edit")
    @htmx_only
    @role_required("ADMIN")
    def users_edit(user_id):
        user = get_user(user_id)
        if user is None:
            abort(404)
        values = {
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email,
            "role": user.role,
        }
        return _render_user_form(
            is_edit=True, user_id=user.id, values=values, errors={}
        )

    @app.post("/users")
    @role_required("ADMIN")
    def users_create():
        try:
            data = UserIn().load(request.form)
        except ValidationError as err:
            return _render_user_form(
                is_edit=False, values=request.form, errors=err.messages, status=422
            )

        try:
            user = create_user(data)
        except IntegrityError:
            db.session.rollback()
            return _render_user_form(
                is_edit=False,
                values=request.form,
                errors=DUPLICATE_FIELD_ERROR,
                status=409,
            )

        return _save_success(user, "created")

    @app.patch("/users/<int:user_id>")
    @role_required("ADMIN")
    def users_update(user_id):
        user = get_user(user_id)
        if user is None:
            abort(404)

        form_data = request.form.to_dict()
        if not form_data.get("password"):
            form_data.pop("password", None)

        try:
            data = UserIn(partial=True).load(form_data)
        except ValidationError as err:
            return _render_user_form(
                is_edit=True,
                user_id=user_id,
                values=request.form,
                errors=err.messages,
                status=422,
            )

        try:
            user = update_user(user, data)
        except IntegrityError:
            db.session.rollback()
            return _render_user_form(
                is_edit=True,
                user_id=user_id,
                values=request.form,
                errors=DUPLICATE_FIELD_ERROR,
                status=409,
            )

        return _save_success(user, "updated")

    @app.get("/users/<int:user_id>/delete/confirm")
    @htmx_only
    @role_required("ADMIN")
    def users_delete_confirm(user_id):
        user = get_user(user_id)
        if user is None:
            abort(404)
        return render_template("partials/users/delete_confirm.html", user=user)

    @app.delete("/users/<int:user_id>")
    @role_required("ADMIN")
    def users_delete(user_id):
        user = get_user(user_id)
        if user is None:
            abort(404)
        if user.id == current_user.id:
            return render_template(
                "partials/users/delete_success.html", users=list_users()
            ) + render_toast("error", "You can't delete your own account.")
        username = user.username
        delete_user(user)
        return render_template(
            "partials/users/delete_success.html", users=list_users()
        ) + render_toast("success", f"User {username} deleted.")
