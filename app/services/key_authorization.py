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


def list_master_keys_with_active_authorizations():
    keys = Key.query.filter_by(is_master_key=True).order_by(Key.id).all()
    key_ids = [k.id for k in keys]
    active = (
        KeyAuthorization.query.filter(
            KeyAuthorization.key_id.in_(key_ids), KeyAuthorization.revoked_at.is_(None)
        )
        .order_by(KeyAuthorization.id)
        .all()
        if key_ids
        else []
    )
    by_key = {}
    for auth in active:
        by_key.setdefault(auth.key_id, []).append(auth)
    return [(key, by_key.get(key.id, [])) for key in keys]


def active_authorizations_for_key(key_id):
    return (
        KeyAuthorization.query.filter_by(key_id=key_id, revoked_at=None)
        .order_by(KeyAuthorization.id)
        .all()
    )


def active_assignee_ids_for_key(key_id):
    return {a.assignee_id for a in active_authorizations_for_key(key_id)}


def diff_authorized_assignees(key_id, assignee_ids):
    current_ids = active_assignee_ids_for_key(key_id)
    target_ids = set(assignee_ids)
    return sorted(target_ids - current_ids), sorted(current_ids - target_ids)


def sync_key_authorizations(key, assigner_id, assignee_ids):
    to_grant_ids, to_revoke_ids = diff_authorized_assignees(key.id, assignee_ids)
    current_by_assignee = {a.assignee_id: a for a in active_authorizations_for_key(key.id)}

    granted = []
    for assignee_id in to_grant_ids:
        granted.append(
            grant_key_authorization(
                {"key_id": key.id, "assignee_id": assignee_id, "assigner_id": assigner_id}
            )
        )

    revoked = []
    for assignee_id in to_revoke_ids:
        revoked.append(revoke_key_authorization(current_by_assignee[assignee_id]))

    return granted, revoked
