from app.routes.booking import register_booking_routes
from app.routes.core import register_core_routes
from app.routes.feature import register_feature_routes
from app.routes.key import register_key_routes
from app.routes.room import register_room_routes
from app.routes.user import register_user_routes


def register_routes(app):
    register_core_routes(app)
    register_user_routes(app)
    register_feature_routes(app)
    register_key_routes(app)
    register_room_routes(app)
    register_booking_routes(app)
