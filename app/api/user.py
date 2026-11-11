from apiflask import APIBlueprint, EmptySchema, abort
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from app import db
from app.schemas.user import UserIn, UserOut
from app.services.audit import log_action
from app.services.auth import role_required
from app.services.user import (
    create_user,
    delete_user,
    get_user,
    list_users,
    update_user,
)

users_blp = APIBlueprint("users", __name__, url_prefix="/api/users", tag="Users")


@users_blp.get("/")
@users_blp.output(UserOut(many=True))
def get_users():
    return list_users()


@users_blp.post("/")
@users_blp.input(UserIn)
@users_blp.output(UserOut, status_code=201)
@role_required("ADMIN")
def create_user_view(json_data):
    try:
        user = create_user(json_data)
        log_action(
            current_user.id if current_user.is_authenticated else None,
            "user.create",
            entity_type="user",
            entity_id=user.id,
        )
        return user
    except IntegrityError:
        db.session.rollback()
        abort(409, message="Username or email already exists.")


@users_blp.get("/<int:user_id>/")
@users_blp.output(UserOut)
def get_user_view(user_id):
    user = get_user(user_id)
    if user is None:
        abort(404, message="User not found.")
    return user


@users_blp.patch("/<int:user_id>/")
@users_blp.input(UserIn(partial=True))
@users_blp.output(UserOut)
@role_required("ADMIN")
def update_user_view(user_id, json_data):
    user = get_user(user_id)
    if user is None:
        abort(404, message="User not found.")
    if (
        user.id == current_user.id
        and json_data.get("role")
        and json_data["role"] != "ADMIN"
    ):
        abort(409, message="You can't change your own role away from Admin.")
    try:
        user = update_user(user, json_data)
        log_action(
            current_user.id if current_user.is_authenticated else None,
            "user.update",
            entity_type="user",
            entity_id=user.id,
        )
        return user
    except IntegrityError:
        db.session.rollback()
        abort(409, message="Username or email already exists.")


@users_blp.delete("/<int:user_id>/")
@users_blp.output(EmptySchema, status_code=204)
@role_required("ADMIN")
def delete_user_view(user_id):
    user = get_user(user_id)
    if user is None:
        abort(404, message="User not found.")
    if user.id == current_user.id:
        abort(409, message="You can't delete your own account.")
    user_id = user.id
    delete_user(user)
    log_action(
        current_user.id if current_user.is_authenticated else None,
        "user.delete",
        entity_type="user",
        entity_id=user_id,
    )
