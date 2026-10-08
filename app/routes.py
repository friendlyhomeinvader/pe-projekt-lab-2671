from flask import abort, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user

from app.services.auth import authenticate
from app.services.nav import can_access_module, find_nav_item, visible_nav_items


def _html_error_handler(template_name, status):
    def handler(_error):
        return render_template(template_name), status

    return handler


def register_routes(app):
    @app.get("/")
    def dashboard():
        if not current_user.is_authenticated:
            return render_template("login.html")
        return render_template(
            "dashboard.html", nav_items=visible_nav_items(current_user.role)
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

    @app.get("/fragments/<module>")
    def fragment(module):
        item = find_nav_item(module)
        if item is None:
            abort(404)
        if not current_user.is_authenticated:
            abort(401)
        if not can_access_module(current_user.role, module):
            abort(403)
        return render_template("partials/coming_soon.html", label=item["label"])

    app.register_error_handler(
        401, _html_error_handler("partials/login_required.html", 401)
    )
    app.register_error_handler(403, _html_error_handler("partials/forbidden.html", 403))
