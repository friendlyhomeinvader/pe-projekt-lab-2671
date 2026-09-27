from app import db


class Preferences(db.Model):
    __tablename__ = "preferences"
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(64), index=True)
    value = db.Column(db.String(256))
    description = db.Column(db.String(256))
