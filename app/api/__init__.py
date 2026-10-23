from app.api.booking import bookings_blp
from app.api.feature import features_blp
from app.api.key import keys_blp
from app.api.key_authorization import key_authorizations_blp
from app.api.room import rooms_blp
from app.api.user import users_blp


def register_api(app):
    app.register_blueprint(users_blp)
    app.register_blueprint(rooms_blp)
    app.register_blueprint(features_blp)
    app.register_blueprint(bookings_blp)
    app.register_blueprint(keys_blp)
    app.register_blueprint(key_authorizations_blp)
