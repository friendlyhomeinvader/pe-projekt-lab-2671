from app import db


class Feature(db.Model):
    __tablename__ = "feature"
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(64), index=True)
    description = db.Column(db.String(256))

    rooms = db.relationship(
        "Room", secondary="rooms_features", back_populates="features"
    )


class RoomFeatureJump(db.Model):
    __tablename__ = "rooms_features"

    room_id = db.Column(db.Integer, db.ForeignKey("room.id"), primary_key=True)
    feature_id = db.Column(db.Integer, db.ForeignKey("feature.id"), primary_key=True)


class Room(db.Model):
    __tablename__ = "room"
    id = db.Column(db.Integer, primary_key=True)

    code = db.Column(db.String(64), index=True)
    location = db.Column(db.String(64), index=True)
    capacity = db.Column(db.Integer, index=True)

    bookings = db.relationship("Booking", back_populates="room", viewonly=True)
    key = db.relationship("Key", back_populates="room")
    keys = db.relationship("Key", back_populates="rooms", secondary="keys_rooms")
    features = db.relationship(
        "Feature", secondary="rooms_features", back_populates="rooms"
    )
    maintenance_slots = db.relationship("MaintenanceSlot", back_populates="room")
    issue_tickets = db.relationship("IssueTicket", back_populates="room")
