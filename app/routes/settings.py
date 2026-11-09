from flask import render_template, request
from flask_login import current_user
from marshmallow import ValidationError

from app.schemas.preferences import PreferencesIn
from app.services.audit import log_action
from app.services.auth import role_required
from app.services.nav import grouped_visible_nav_items
from app.services.notify import render_toast
from app.services.page import render_page
from app.services.preferences import (
    get_no_show_grace_minutes,
    set_no_show_grace_minutes,
)


def _current_values():
    return {"no_show_grace_minutes": get_no_show_grace_minutes()}


def register_settings_routes(app):
    @app.get("/settings")
    @role_required("ADMIN")
    def settings_page():
        return render_page(
            "partials/settings/form.html",
            nav_groups=grouped_visible_nav_items(current_user.role),
            title="Settings",
            values=_current_values(),
            errors={},
        )

    @app.patch("/settings")
    @role_required("ADMIN")
    def settings_update():
        try:
            data = PreferencesIn().load(request.form)
        except ValidationError as err:
            return render_template(
                "partials/settings/form.html",
                values=request.form,
                errors=err.messages,
            ), 422

        pref = set_no_show_grace_minutes(data["no_show_grace_minutes"])
        log_action(
            current_user.id,
            "preferences.update",
            entity_type="preference",
            entity_id=pref.id,
            details=f"no_show_grace_minutes={data['no_show_grace_minutes']}",
        )

        return render_template(
            "partials/settings/form.html",
            values=_current_values(),
            errors={},
        ) + render_toast("success", "Settings updated.")
