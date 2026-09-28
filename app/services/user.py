from app.models.user import User


def list_users():
    return User.query.order_by(User.id).all()
