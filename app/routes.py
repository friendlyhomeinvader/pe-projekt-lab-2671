from flask import abort, render_template

NAV_ITEMS = [
    {"slug": "booking", "label": "Booking"},
]


def register_routes(app):
    @app.get("/")
    def dashboard():
        return render_template("dashboard.html", nav_items=NAV_ITEMS)

    @app.get("/fragments/<module>")
    def fragment(module):
        item = next((i for i in NAV_ITEMS if i["slug"] == module), None)
        if item is None:
            abort(404)
        return render_template("partials/coming_soon.html", label=item["label"])
