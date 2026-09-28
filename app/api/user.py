from apiflask import APIBlueprint
from app.schemas.user import UserOut

from app.services.user import list_users

users_blp = APIBlueprint(
    "users", __name__, url_prefix="/api/users", tag="Users")


@users_blp.get("/")
@users_blp.output(UserOut(many=True))
def get_users():
    return list_users()
