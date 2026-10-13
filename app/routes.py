from flask import abort, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app import db
from app.models.user import USER_ROLES
from app.schemas.feature import FeatureIn
from app.schemas.room import RoomIn
from app.schemas.user import UserIn
from app.services.auth import authenticate, role_required
from app.services.feature import (
    create_feature,
    delete_feature,
    get_feature,
    list_features,
    update_feature,
)
from app.services.nav import (
    can_access_module,
    find_nav_item,
    grouped_visible_nav_items,
)
from app.services.notify import render_toast
from app.services.preferences import is_installed, mark_installed
from app.services.room import (
    create_room,
    delete_room,
    get_room,
    list_rooms,
    update_room,
)
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


def _render_feature_form(*, is_edit, values, errors, feature_id=None, status=200):
    kwargs = {
        "is_edit": is_edit,
        "values": values,
        "errors": errors,
    }
    if feature_id is not None:
        kwargs["feature_id"] = feature_id
    html = render_template("partials/features/form.html", **kwargs)
    return (html, status) if status != 200 else html


def _feature_save_success(feature, verb):
    return render_template(
        "partials/features/save_success.html", features=list_features()
    ) + render_toast("success", f"Feature {feature.name} {verb}.")


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


def _html_error_handler(template_name, status):
    def handler(_error):
        return render_template(template_name), status

    return handler


def register_routes(app):
    @app.before_request
    def _require_install():
        if request.path.startswith(("/api/", "/docs", "/openapi")):
            return None
        if request.endpoint in (
            "install",
            "install_create",
            "static",
            "check_health",
            "db_health",
        ):
            return None
        if not is_installed():
            return redirect(url_for("install"))

    @app.get("/install")
    def install():
        if is_installed():
            return redirect(url_for("dashboard"))
        return render_template("install.html", values={}, errors={})

    @app.post("/install")
    def install_create():
        if is_installed():
            return redirect(url_for("dashboard"))
        data = dict(request.form)
        data["role"] = "ADMIN"
        try:
            validated = UserIn().load(data)
        except ValidationError as err:
            return render_template(
                "install.html", values=request.form, errors=err.messages
            ), 422
        user = create_user(validated)
        mark_installed()
        login_user(user)
        return redirect(url_for("dashboard"))

    @app.get("/")
    def dashboard():
        if not current_user.is_authenticated:
            return render_template("login.html")
        return render_template(
            "dashboard.html", nav_groups=grouped_visible_nav_items(current_user.role)
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
        if module == "room-management":
            return render_template("partials/room_management.html", rooms=list_rooms())
        return render_template("partials/coming_soon.html", label=item["label"])

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
        if user.id == current_user.id:
            return render_template(
                "partials/users/delete_success.html", users=list_users()
            ) + render_toast("error", "You can't delete your own account.")
        username = user.username
        delete_user(user)
        return render_template(
            "partials/users/delete_success.html", users=list_users()
        ) + render_toast("success", f"User {username} deleted.")

    @app.get("/features")
    @role_required("ADMIN")
    def features_list():
        return render_template("partials/features/list.html", features=list_features())

    @app.get("/features/new")
    @role_required("ADMIN")
    def features_new():
        return _render_feature_form(is_edit=False, values={}, errors={})

    @app.get("/features/<int:feature_id>/edit")
    @role_required("ADMIN")
    def features_edit(feature_id):
        feature = get_feature(feature_id)
        if feature is None:
            abort(404)
        values = {"name": feature.name, "description": feature.description}
        return _render_feature_form(
            is_edit=True, feature_id=feature.id, values=values, errors={}
        )

    @app.post("/features")
    @role_required("ADMIN")
    def features_create():
        try:
            data = FeatureIn().load(request.form)
        except ValidationError as err:
            return _render_feature_form(
                is_edit=False, values=request.form, errors=err.messages, status=422
            )

        feature = create_feature(data)
        return _feature_save_success(feature, "created")

    @app.patch("/features/<int:feature_id>")
    @role_required("ADMIN")
    def features_update(feature_id):
        feature = get_feature(feature_id)
        if feature is None:
            abort(404)

        try:
            data = FeatureIn(partial=True).load(request.form)
        except ValidationError as err:
            return _render_feature_form(
                is_edit=True,
                feature_id=feature_id,
                values=request.form,
                errors=err.messages,
                status=422,
            )

        feature = update_feature(feature, data)
        return _feature_save_success(feature, "updated")

    @app.get("/features/<int:feature_id>/delete/confirm")
    @role_required("ADMIN")
    def features_delete_confirm(feature_id):
        feature = get_feature(feature_id)
        if feature is None:
            abort(404)
        return render_template("partials/features/delete_confirm.html", feature=feature)

    @app.delete("/features/<int:feature_id>")
    @role_required("ADMIN")
    def features_delete(feature_id):
        feature = get_feature(feature_id)
        if feature is None:
            abort(404)
        name = feature.name
        try:
            delete_feature(feature)
        except SQLAlchemyError:
            db.session.rollback()
            return (
                render_template(
                    "partials/features/delete_success.html", features=list_features()
                )
                + render_toast("error", "Failed to delete feature. Please try again."),
                500,
            )
        return render_template(
            "partials/features/delete_success.html", features=list_features()
        ) + render_toast("success", f"Feature {name} deleted.")

    @app.get("/rooms")
    @role_required("ADMIN")
    def rooms_list():
        return render_template("partials/rooms/list.html", rooms=list_rooms())

    @app.get("/rooms/new")
    @role_required("ADMIN")
    def rooms_new():
        return _render_room_form(is_edit=False, values={}, errors={})

    @app.get("/rooms/<int:room_id>/edit")
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
                errors={"feature_ids": [str(err)]},
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
                errors={"feature_ids": [str(err)]},
                status=422,
            )

        return _room_save_success(room, "updated")

    @app.get("/rooms/<int:room_id>/delete/confirm")
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
