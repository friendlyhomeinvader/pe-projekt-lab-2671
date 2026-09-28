from apiflask import APIBlueprint, EmptySchema, abort
from sqlalchemy.exc import IntegrityError

from app import db

from app.schemas.user import UserOut, UserIn
from app.services.user import list_users, create_user, get_user, update_user, delete_user

users_blp = APIBlueprint("users", __name__, url_prefix="/api/users", tag="Users")


@users_blp.get("/")
@users_blp.output(UserOut(many=True))
def get_users():
    return list_users()


@users_blp.post("/")
@users_blp.input(UserIn)
@users_blp.output(UserOut, status_code=201)
def create_user_view(json_data):
    try:
        user = create_user(json_data)
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
def update_user_view(user_id, json_data):
    user = get_user(user_id)
    if user is None:
        abort(404, message="User not found.")
    try:
        user = update_user(user, json_data)
        return user
    except IntegrityError:
        db.session.rollback()
        abort(409, message="Username or email already exists.")


@users_blp.delete("/<int:user_id>/")
@users_blp.output(EmptySchema, status_code=204)
def delete_user_view(user_id):
    user = get_user(user_id)
    if user is None:
        abort(404, message="User not found.")
    delete_user(user)
