from app.routes.audit import register_audit_routes
from app.routes.booking import register_booking_routes
from app.routes.core import register_core_routes
from app.routes.feature import register_feature_routes
from app.routes.key import register_key_routes
from app.routes.key_handling import register_key_handling_routes
from app.routes.key_transaction import register_key_transaction_routes
from app.routes.maintenance import register_maintenance_routes
from app.routes.room import register_room_routes
from app.routes.settings import register_settings_routes
from app.routes.user import register_user_routes


def register_routes(app):
    register_core_routes(app)
    register_audit_routes(app)
    register_user_routes(app)
    register_feature_routes(app)
    register_key_routes(app)
    register_key_handling_routes(app)
    register_key_transaction_routes(app)
    register_room_routes(app)
    register_booking_routes(app)
    register_settings_routes(app)
    register_maintenance_routes(app)
