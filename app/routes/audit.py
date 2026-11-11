from flask_login import current_user

from app.services.audit import list_audit_logs
from app.services.auth import role_required
from app.services.nav import grouped_visible_nav_items
from app.services.page import render_page


def register_audit_routes(app):
    @app.get("/reports-audit")
    @role_required("AUDITOR")
    def reports_audit_page():
        return render_page(
            "partials/audit/list.html",
            nav_groups=grouped_visible_nav_items(current_user.role),
            title="Reports / Audit",
            logs=list_audit_logs(),
        )
