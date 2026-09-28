from app import db

ISSUE_TICKET_STATES = ("OPEN", "IN_PROGRESS", "RESOLVED")


class IssueTicket(db.Model):
    __tablename__ = "issue_ticket"

    id = db.Column(db.Integer, primary_key=True)

    room_id = db.Column(db.Integer, db.ForeignKey("room.id"), nullable=True)
    key_id = db.Column(db.Integer, db.ForeignKey("key.id"), nullable=True)
    reported_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    operator_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    resolved_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    description = db.Column(db.String(512), nullable=False)
    state = db.Column(db.String(16), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)

    room = db.relationship("Room", back_populates="issue_tickets")
    key = db.relationship("Key", back_populates="issue_tickets")
    reported_by = db.relationship("User", foreign_keys="reported_by_id")
    operator = db.relationship("User", foreign_keys="operator_id")
    resolved_by = db.relationship("User", foreign_keys="resolved_by_id")

    __table_args__ = (
        db.CheckConstraint(
            f"state in ({', '.join(f"'{x}'" for x in ISSUE_TICKET_STATES)})",
            "ck_allowed_issue_ticket_states",
        ),
    )
