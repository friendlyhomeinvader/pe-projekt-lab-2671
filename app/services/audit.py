from datetime import datetime, timezone

from app import db
from app.models.audit_log import AuditLog

DEFAULT_LIST_LIMIT = 200


def list_audit_logs(limit=DEFAULT_LIST_LIMIT):
    return (
        AuditLog.query.order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
        .limit(limit)
        .all()
    )


def log_action(actor_id, action, entity_type=None, entity_id=None, details=None):
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.session.add(entry)
    db.session.commit()
    return entry
