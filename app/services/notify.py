from flask import render_template

TOAST_LEVELS = ("success", "info", "warning", "error")


def render_toast(level, message):
    if level not in TOAST_LEVELS:
        raise ValueError(f"What level? He: {level}")
    return render_template("partials/toast.html", level=level, message=message)
