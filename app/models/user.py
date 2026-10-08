from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db

USER_ROLES = ("REQUESTER", "OPERATOR", "ADMIN", "AUDITOR")
USER_IDENTIFICATION_METHODS = ("PIN", "CARD", "SIGNATURE")


class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(64), nullable=False, unique=True, index=True)
    display_name = db.Column(db.String(256), nullable=False)
    email = db.Column(db.String(256), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(16), nullable=False)

    user_identification_id = db.Column(
        db.Integer, db.ForeignKey("user_identification.id")
    )

    user_identification = db.relationship("UserIdentification")
    bookings = db.relationship("Booking", back_populates="requester")
    master_key_authorizations = db.relationship(
        "KeyAuthorization",
        back_populates="assignee",
        foreign_keys="KeyAuthorization.assignee_id",
    )
    master_keys = db.relationship(
        "Key",
        secondary="key_authorization",
        primaryjoin="KeyAuthorization.assignee_id == User.id",
        secondaryjoin="Key.id == KeyAuthorization.key_id",
        viewonly=True,
    )

    __table_args__ = (
        db.CheckConstraint(
            f"role in ({', '.join(f"'{x}'" for x in USER_ROLES)})",
            name="ck_allowed_role",
        ),
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class UserIdentification(db.Model):
    __tablename__ = "user_identification"
    id = db.Column(db.Integer, primary_key=True)

    type = db.Column(db.String(16), nullable=False)
    value = db.Column(db.String(256), nullable=False)
    __table_args__ = (
        db.CheckConstraint(
            f"type in ({', '.join(f"'{x}'" for x in USER_IDENTIFICATION_METHODS)})",
            name="ck_allowed_identification_method",
        ),
    )
