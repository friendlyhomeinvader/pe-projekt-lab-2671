from functools import wraps

from flask import abort, render_template, request


def render_page(fragment_template, *, nav_groups, title, **context):
    fragment = render_template(fragment_template, **context)
    if request.headers.get("HX-Request"):
        return fragment
    return render_template("page.html", content=fragment, nav_groups=nav_groups, title=title)


def htmx_only(view_func):
    """Reject a plain GET on a fragment-only endpoint that isn't backed by a real page."""

    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not request.headers.get("HX-Request"):
            abort(404)
        return view_func(*args, **kwargs)

    return wrapper
