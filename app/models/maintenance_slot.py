from app import db


class MaintenanceSlot(db.Model):
    __tablename__ = "maintenance_slot"

    id = db.Column(db.Integer, primary_key=True)

    room_id = db.Column(db.Integer, db.ForeignKey("room.id"))
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.String(256), nullable=True)

    room = db.relationship("Room", back_populates="maintenance_slots")
    created_by = db.relationship("User")
