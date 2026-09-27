from app import db

BOOKING_STATES = ("PENDING", "ACTIVE", "NO_SHOW", "FINISHED")


class Booking(db.Model):
    __tablename__ = "booking"

    id = db.Column(db.Integer, primary_key=True)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    state = db.Column(db.String(16), nullable=False)

    requester_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    room_id = db.Column(db.Integer, db.ForeignKey("room.id"))

    requester = db.relationship("User", back_populates="bookings")
    room = db.relationship("Room", back_populates="bookings")
    key_transactions = db.relationship("KeyTransaction", back_populates="booking")

    __table_args__ = (
        db.CheckConstraint(
            f"state in ({', '.join(f"'{x}'" for x in BOOKING_STATES)})",
            "ck_allowed_states",
        ),
    )
