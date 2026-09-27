from app import db

KEY_TRANSACTION_STATES = ("ISSUED", "RETURNED")


class KeyTransaction(db.Model):
    __tablename__ = "key_transaction"

    id = db.Column(db.Integer, primary_key=True)

    key_id = db.Column(db.Integer, db.ForeignKey("key.id"))
    booking_id = db.Column(db.Integer, db.ForeignKey("booking.id"), nullable=True)
    holder_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    operator_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    identification_id = db.Column(db.Integer, db.ForeignKey("user_identification.id"))

    state = db.Column(db.String(16), nullable=False)
    issued_at = db.Column(db.DateTime, nullable=False)
    returned_at = db.Column(db.DateTime, nullable=True)
    room_condition_notes = db.Column(db.String(256), nullable=True)
    damage_reported = db.Column(db.Boolean, index=True, default=False)

    key = db.relationship("Key", back_populates="transactions")
    booking = db.relationship("Booking", back_populates="key_transactions")
    holder = db.relationship("User", foreign_keys="KeyTransaction.holder_id")
    operator = db.relationship("User", foreign_keys="KeyTransaction.operator_id")
    identification = db.relationship("UserIdentification")

    __table_args__ = (
        db.CheckConstraint(
            f"state in ({', '.join(f"'{x}'" for x in KEY_TRANSACTION_STATES)})",
            "ck_allowed_key_transaction_states",
        ),
    )
