from flask import abort, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from marshmallow import ValidationError

from app.schemas.user import UserIn
from app.services.auth import authenticate
from app.services.nav import can_access_module, find_nav_item, grouped_visible_nav_items
from app.services.page import render_page
from app.services.preferences import is_installed, mark_installed
from app.services.user import create_user


def _html_error_handler(template_name, status):
    def handler(_error):
        return render_template(template_name), status

    return handler


def register_core_routes(app):
    @app.before_request
    def _require_install():
        if request.path.startswith("/api/"):
            return None
        if request.endpoint in (
            "install",
            "install_create",
            "static",
            "check_health",
            "db_health",
        ):
            return None
        if not is_installed():
            return redirect(url_for("install"))

    @app.get("/install")
    def install():
        if is_installed():
            return redirect(url_for("dashboard"))
        return render_template("install.html", values={}, errors={})

    @app.post("/install")
    def install_create():
        if is_installed():
            return redirect(url_for("dashboard"))
        data = dict(request.form)
        data["role"] = "ADMIN"
        try:
            validated = UserIn().load(data)
        except ValidationError as err:
            return render_template(
                "install.html", values=request.form, errors=err.messages
            ), 422
        user = create_user(validated)
        mark_installed()
        login_user(user)
        return redirect(url_for("dashboard"))

    @app.get("/")
    def dashboard():
        if not current_user.is_authenticated:
            return render_template("login.html")
        return render_template(
            "dashboard.html", nav_groups=grouped_visible_nav_items(current_user.role)
        )

    @app.post("/login")
    def login():
        user = authenticate(
            request.form.get("username", ""), request.form.get("password", "")
        )
        if user is None:
            return render_template(
                "login.html", error="Invalid username or password."
            ), 401
        login_user(user)
        return redirect(url_for("dashboard"))

    @app.get("/logout")
    def logout():
        logout_user()
        return redirect(url_for("dashboard"))

    @app.get("/<module>")
    def nav_page(module):
        item = find_nav_item(module)
        if item is None:
            abort(404)
        if not current_user.is_authenticated:
            abort(401)
        if not can_access_module(current_user.role, module):
            abort(403)
        return render_page(
            "partials/coming_soon.html",
            nav_groups=grouped_visible_nav_items(current_user.role),
            title=item["label"],
            label=item["label"],
        )

    app.register_error_handler(
        401, _html_error_handler("partials/login_required.html", 401)
    )
    app.register_error_handler(403, _html_error_handler("partials/forbidden.html", 403))
