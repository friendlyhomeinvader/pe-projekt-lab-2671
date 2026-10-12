from app import db
from app.models.room import Feature


def list_features():
    return Feature.query.order_by(Feature.id).all()


def get_feature(feature_id):
    return db.session.get(Feature, feature_id)


def create_feature(data):
    feature = Feature(
        name=data["name"],
        description=data.get("description"),
    )
    db.session.add(feature)
    db.session.commit()
    return feature


def update_feature(feature, data):
    for field in ("name", "description"):
        if field in data:
            setattr(feature, field, data[field])
    db.session.commit()
    return feature


def delete_feature(feature):
    db.session.delete(feature)
    db.session.commit()
