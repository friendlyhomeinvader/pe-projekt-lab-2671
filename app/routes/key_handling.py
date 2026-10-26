from flask import render_template
from flask_login import current_user

from app.services.auth import role_required
from app.services.booking import list_in_progress_and_upcoming_bookings
from app.services.key import list_authorized_keys
from app.services.key_authorization import active_authorizations_by_key_id
from app.services.nav import grouped_visible_nav_items
from app.services.page import htmx_only, render_page


def register_key_handling_routes(app):
    @app.get("/key-handling")
    @role_required("OPERATOR")
    def key_handling_page():
        keys = list_authorized_keys()
        return render_page(
            "partials/key_handling.html",
            nav_groups=grouped_visible_nav_items(current_user.role),
            title="Key Handling",
            keys=keys,
            authorizations_by_key=active_authorizations_by_key_id(
                [k.id for k in keys if k.is_master_key]
            ),
            booking_rows=list_in_progress_and_upcoming_bookings(),
        )

    @app.get("/key-handling/keys")
    @htmx_only
    @role_required("OPERATOR")
    def key_handling_keys_list():
        keys = list_authorized_keys()
        return render_template(
            "partials/key_handling/keys_list.html",
            keys=keys,
            authorizations_by_key=active_authorizations_by_key_id(
                [k.id for k in keys if k.is_master_key]
            ),
        )

    @app.get("/key-handling/bookings")
    @htmx_only
    @role_required("OPERATOR")
    def key_handling_bookings_list():
        return render_template(
            "partials/key_handling/bookings_list.html",
            booking_rows=list_in_progress_and_upcoming_bookings(),
        )
