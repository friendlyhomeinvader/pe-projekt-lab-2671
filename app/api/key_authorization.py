from apiflask import APIBlueprint, abort
from flask_login import current_user

from app.schemas.key_authorization import KeyAuthorizationGrantIn, KeyAuthorizationOut
from app.services.audit import log_action
from app.services.auth import role_required
from app.services.key_authorization import (
    get_key_authorization,
    grant_key_authorization,
    list_key_authorizations,
    revoke_key_authorization,
)

key_authorizations_blp = APIBlueprint(
    "key_authorizations",
    __name__,
    url_prefix="/api/key-authorizations",
    tag="Key Authorizations",
)


@key_authorizations_blp.get("/")
@key_authorizations_blp.output(KeyAuthorizationOut(many=True))
def get_key_authorizations():
    return list_key_authorizations()


@key_authorizations_blp.get("/<int:authorization_id>/")
@key_authorizations_blp.output(KeyAuthorizationOut)
def get_key_authorization_view(authorization_id):
    authorization = get_key_authorization(authorization_id)
    if authorization is None:
        abort(404, message="Authorization not found.")
    return authorization


@key_authorizations_blp.post("/grant")
@key_authorizations_blp.input(KeyAuthorizationGrantIn)
@key_authorizations_blp.output(KeyAuthorizationOut, status_code=201)
@role_required("ADMIN")
def grant_key_authorization_view(json_data):
    try:
        authorization = grant_key_authorization(json_data)
        log_action(
            current_user.id if current_user.is_authenticated else None,
            "key_authorization.grant",
            entity_type="key_authorization",
            entity_id=authorization.id,
        )
        return authorization
    except ValueError as err:
        abort(422, message=str(err))


@key_authorizations_blp.post("/<int:authorization_id>/revoke")
@key_authorizations_blp.output(KeyAuthorizationOut)
@role_required("ADMIN")
def revoke_key_authorization_view(authorization_id):
    authorization = get_key_authorization(authorization_id)
    if authorization is None:
        abort(404, message="Authorization not found.")
    try:
        authorization = revoke_key_authorization(authorization)
        log_action(
            current_user.id if current_user.is_authenticated else None,
            "key_authorization.revoke",
            entity_type="key_authorization",
            entity_id=authorization.id,
        )
        return authorization
    except ValueError as err:
        abort(422, message=str(err))
