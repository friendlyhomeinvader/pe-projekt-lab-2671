from app import db


class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)

    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    action = db.Column(db.String(64), index=True, nullable=False)
    entity_type = db.Column(db.String(32), index=True, nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.String(512), nullable=True)
    occurred_at = db.Column(db.DateTime, index=True, nullable=False)

    actor = db.relationship("User")
