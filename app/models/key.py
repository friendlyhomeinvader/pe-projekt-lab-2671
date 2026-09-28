from app import db


class Key(db.Model):
    __tablename__ = "key"
    id = db.Column(db.Integer, primary_key=True)

    tag = db.Column(db.String(64), index=True)
    is_master_key = db.Column(db.Boolean, index=True)

    room_id = db.Column(db.Integer, db.ForeignKey("room.id"))

    room = db.relationship("Room", back_populates="key")
    rooms = db.relationship("Room", back_populates="keys", secondary="keys_rooms")
    allowed_holders = db.relationship(
        "User",
        secondary="key_authorization",
        primaryjoin="Key.id == KeyAuthorization.key_id",
        secondaryjoin="KeyAuthorization.assignee_id == User.id",
        viewonly=True,
    )
    transactions = db.relationship("KeyTransaction", back_populates="key")
    issue_tickets = db.relationship("IssueTicket", back_populates="key")


class KeyRoomJump(db.Model):
    __tablename__ = "keys_rooms"
    key_id = db.Column(db.Integer, db.ForeignKey("key.id"), primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey("room.id"), primary_key=True)


class KeyAuthorization(db.Model):
    __tablename__ = "key_authorization"
    id = db.Column(db.Integer, primary_key=True)

    key_id = db.Column(db.Integer, db.ForeignKey("key.id"))
    assignee_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    assigner_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    granted_at = db.Column(db.DateTime)
    revoked_at = db.Column(db.DateTime, nullable=True)

    assignee = db.relationship(
        "User",
        back_populates="master_key_authorizations",
        foreign_keys="KeyAuthorization.assignee_id",
    )
    assigner = db.relationship("User", foreign_keys="KeyAuthorization.assigner_id")
