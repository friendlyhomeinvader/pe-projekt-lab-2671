from flask import abort, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.user import USER_ROLES
from app.schemas.user import UserIn
from app.services.auth import authenticate, role_required
from app.services.nav import can_access_module, find_nav_item, visible_nav_items
from app.services.notify import render_toast
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


def _html_error_handler(template_name, status):
    def handler(_error):
        return render_template(template_name), status

    return handler


def register_routes(app):
    @app.get("/")
    def dashboard():
        if not current_user.is_authenticated:
            return render_template("login.html")
        return render_template(
            "dashboard.html", nav_items=visible_nav_items(current_user.role)
        )

    @app.post("/login")
    def login():
        user = authenticate(
            request.form.get("username", ""), request.form.get("password", "")
        )
        if user is None:
            return render_template(
                "login.html", error="Invalid username or password."
            ), 401
        login_user(user)
        return redirect(url_for("dashboard"))

    @app.get("/logout")
    def logout():
        logout_user()
        return redirect(url_for("dashboard"))

    @app.get("/fragments/<module>")
    def fragment(module):
        item = find_nav_item(module)
        if item is None:
            abort(404)
        if not current_user.is_authenticated:
            abort(401)
        if not can_access_module(current_user.role, module):
            abort(403)
        if module == "user-management":
            return render_template("partials/users/list.html", users=list_users())
        return render_template("partials/coming_soon.html", label=item["label"])

    @app.get("/toast/dismiss")
    def toast_dismiss():
        return ""

    app.register_error_handler(
        401, _html_error_handler("partials/login_required.html", 401)
    )
    app.register_error_handler(403, _html_error_handler("partials/forbidden.html", 403))

    @app.get("/users/new")
    @role_required("ADMIN")
    def users_new():
        return _render_user_form(is_edit=False, values={}, errors={})

    @app.get("/users/<int:user_id>/edit")
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
        username = user.username
        delete_user(user)
        return render_template(
            "partials/users/delete_success.html", users=list_users()
        ) + render_toast("success", f"User {username} deleted.")
