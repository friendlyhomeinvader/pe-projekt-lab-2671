from app import db
from app.models.preferences import Preferences


def get_preference(name, default=None):
    pref = Preferences.query.filter_by(name=name).first()
    return pref.value if pref is not None else default


def set_preference(name, value, description=None):
    pref = Preferences.query.filter_by(name=name).first()
    if pref is None:
        pref = Preferences(name=name)
        db.session.add(pref)
    pref.value = str(value)
    if description is not None:
        pref.description = description
    db.session.commit()
    return pref


def is_installed():
    return get_preference("installed") == "true"


def mark_installed():
    set_preference(
        "installed",
        "true",
        description="Whether the first-run install flow has completed.",
    )


def mark_uninstalled():
    set_preference(
        "installed",
        "false",
        description="Whether the first-run install flow has completed.",
    )
