from app import db

from app.models.user import User


def list_users():
    return User.query.order_by(User.id).all()


def get_user(user_id):
    return db.session.get(User, user_id)


def create_user(data):
    user = User(
        username=data["username"],
        display_name=data["display_name"],
        email=data["email"],
        role=data["role"],
    )
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()
    return user


def update_user(user, data):
    for field in ("username", "display_name", "email", "role"):
        if field in data:
            setattr(user, field, data[field])
    if "password" in data:
        user.set_password(data["password"])
    db.session.commit()
    return user


def delete_user(user):
    db.session.delete(user)
    db.session.commit()
