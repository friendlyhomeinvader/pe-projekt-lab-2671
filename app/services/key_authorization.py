from datetime import datetime, timezone

from app import db
from app.models.key import Key, KeyAuthorization
from app.models.user import User


def list_key_authorizations():
    return KeyAuthorization.query.order_by(KeyAuthorization.id).all()


def get_key_authorization(authorization_id):
    return db.session.get(KeyAuthorization, authorization_id)


def _resolve_key(key_id):
    key = db.session.get(Key, key_id)
    if key is None:
        raise ValueError(f"Unknown key id: {key_id}")
    return key


def _resolve_user(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        raise ValueError(f"Unknown user id: {user_id}")
    return user


def grant_key_authorization(data):
    key = _resolve_key(data["key_id"])
    if key.is_master_key is not True:
        raise ValueError("Only a master key can be granted to a holder.")

    _resolve_user(data["assignee_id"])
    _resolve_user(data["assigner_id"])

    existing = KeyAuthorization.query.filter_by(
        key_id=data["key_id"], assignee_id=data["assignee_id"], revoked_at=None
    ).first()
    if existing is not None:
        raise ValueError("This assignee already has an active authorization for this key.")

    authorization = KeyAuthorization(
        key_id=data["key_id"],
        assignee_id=data["assignee_id"],
        assigner_id=data["assigner_id"],
        granted_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.session.add(authorization)
    db.session.commit()
    return authorization


def revoke_key_authorization(authorization):
    if authorization.revoked_at is not None:
        raise ValueError("Authorization is already revoked.")

    authorization.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    return authorization
