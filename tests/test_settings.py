import itertools
from datetime import datetime, timedelta, timezone

from app import db
from app.models.audit_log import AuditLog
from app.models.booking import Booking
from app.models.preferences import Preferences
from app.models.room import Room
from app.models.user import User
from app.services.no_show import apply_no_shows
from app.services.preferences import (
    DEFAULT_NO_SHOW_GRACE_MINUTES,
    get_no_show_grace_minutes,
    mark_installed,
    set_no_show_grace_minutes,
)
from tests.helpers import assert_status

_counter = itertools.count()

NOW = datetime.now(timezone.utc).replace(tzinfo=None)


def _create_user(role, **overrides):
    n = next(_counter)
    defaults = {
        "username": f"settings.user.{n}",
        "display_name": f"Settings User {n}",
        "email": f"settings.user.{n}@uni.su",
    }
    defaults.update(overrides)
    user = User(role=role, **defaults)
    user.set_password("Password123456!!")
    db.session.add(user)
    db.session.commit()
    return user


def _create_room(**overrides):
    n = next(_counter)
    defaults = {"code": f"ST{n}", "location": "Building Settings", "capacity": 10}
    defaults.update(overrides)
    room = Room(**defaults)
    db.session.add(room)
    db.session.commit()
    return room


def _create_booking(**overrides):
    requester = overrides.pop("requester", None) or _create_user("REQUESTER")
    room = overrides.pop("room", None) or _create_room()
    defaults = {
        "start_date": NOW - timedelta(hours=1),
        "end_date": NOW + timedelta(hours=1),
        "state": "PENDING",
        "requester_id": requester.id,
        "room_id": room.id,
    }
    defaults.update(overrides)
    booking = Booking(**defaults)
    db.session.add(booking)
    db.session.commit()
    return booking


def test_get_no_show_grace_minutes_default_when_unset(client):
    assert get_no_show_grace_minutes() == DEFAULT_NO_SHOW_GRACE_MINUTES
    assert DEFAULT_NO_SHOW_GRACE_MINUTES == 15


def test_set_no_show_grace_minutes_persists_and_is_read_back(client):
    set_no_show_grace_minutes(5)

    assert get_no_show_grace_minutes() == 5


def test_set_no_show_grace_minutes_stores_row_as_strings(client):
    set_no_show_grace_minutes(5)

    pref = Preferences.query.filter_by(name="no_show_grace_minutes").first()
    assert pref is not None
    assert pref.name == "no_show_grace_minutes"
    assert pref.value == "5"


def test_get_settings_rejects_unauthenticated(client):
    mark_installed()

    response = client.get("/settings")

    assert_status(response, 401)


def test_get_settings_rejects_non_admin(client, login_as):
    login_as("REQUESTER")

    response = client.get("/settings")

    assert_status(response, 403)


def test_get_settings_admin_sees_current_default_value(client, login_as):
    login_as("ADMIN")

    response = client.get("/settings")

    assert_status(response, 200)
    body = response.get_data(as_text=True)
    assert f'value="{DEFAULT_NO_SHOW_GRACE_MINUTES}"' in body


def test_patch_settings_valid_value_persists_and_shows_success_toast(client, login_as):
    login_as("ADMIN")

    response = client.patch("/settings", data={"no_show_grace_minutes": "10"})

    assert_status(response, 200)
    assert get_no_show_grace_minutes() == 10
    assert "Settings updated." in response.get_data(as_text=True)


def test_patch_settings_zero_is_rejected_and_leaves_value_unchanged(client, login_as):
    login_as("ADMIN")
    set_no_show_grace_minutes(15)

    response = client.patch("/settings", data={"no_show_grace_minutes": "0"})

    assert_status(response, 422)
    assert get_no_show_grace_minutes() == 15
    assert "Must be at least 1 minute." in response.get_data(as_text=True)


def test_patch_settings_negative_is_rejected_and_leaves_value_unchanged(
    client, login_as
):
    login_as("ADMIN")
    set_no_show_grace_minutes(15)

    response = client.patch("/settings", data={"no_show_grace_minutes": "-5"})

    assert_status(response, 422)
    assert get_no_show_grace_minutes() == 15
    assert "Must be at least 1 minute." in response.get_data(as_text=True)


def test_patch_settings_non_numeric_is_rejected_and_leaves_value_unchanged(
    client, login_as
):
    login_as("ADMIN")
    set_no_show_grace_minutes(15)

    response = client.patch("/settings", data={"no_show_grace_minutes": "abc"})

    assert_status(response, 422)
    assert get_no_show_grace_minutes() == 15
    assert "no_show_grace_minutes" in response.get_data(as_text=True)


def test_patch_settings_rejects_unauthenticated(client):
    mark_installed()

    response = client.patch("/settings", data={"no_show_grace_minutes": "10"})

    assert_status(response, 401)


def test_patch_settings_rejects_non_admin(client, login_as):
    login_as("OPERATOR")

    response = client.patch("/settings", data={"no_show_grace_minutes": "10"})

    assert_status(response, 403)


def test_patch_settings_success_writes_audit_log(client, login_as):
    admin = login_as("ADMIN")

    response = client.patch("/settings", data={"no_show_grace_minutes": "7"})

    assert_status(response, 200)
    entries = AuditLog.query.filter_by(action="preferences.update").all()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.entity_type == "preference"
    assert entry.actor_id == admin.id
    assert "no_show_grace_minutes=7" in entry.details


def test_patch_settings_validation_failure_writes_no_audit_log(client, login_as):
    login_as("ADMIN")

    response = client.patch("/settings", data={"no_show_grace_minutes": "0"})

    assert_status(response, 422)
    assert AuditLog.query.filter_by(action="preferences.update").count() == 0


def test_patch_settings_grace_period_change_is_honored_immediately_by_no_show_sweep(
    client, login_as
):
    login_as("ADMIN")
    booking = _create_booking(state="PENDING", start_date=NOW - timedelta(minutes=3))

    response = client.patch("/settings", data={"no_show_grace_minutes": "2"})
    assert_status(response, 200)

    changed = apply_no_shows(now=NOW)

    assert [b.id for b in changed] == [booking.id]
    assert booking.state == "NO_SHOW"
