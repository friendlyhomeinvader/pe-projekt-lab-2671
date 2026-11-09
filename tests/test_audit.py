import itertools
from datetime import datetime, timedelta, timezone

from app import db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.audit import list_audit_logs
from app.services.preferences import mark_installed
from tests.helpers import assert_status

_counter = itertools.count()

NOW = datetime.now(timezone.utc).replace(tzinfo=None)


def _create_user(**overrides):
    n = next(_counter)
    defaults = {
        "username": f"audit.user.{n}",
        "display_name": f"Audit User {n}",
        "email": f"audit.user.{n}@uni.su",
        "role": "REQUESTER",
    }
    defaults.update(overrides)
    user = User(**defaults)
    user.set_password("Password123456!!")
    db.session.add(user)
    db.session.commit()
    return user


def _create_log(**overrides):
    n = next(_counter)
    defaults = {
        "actor_id": None,
        "action": f"test.action.{n}",
        "entity_type": None,
        "entity_id": None,
        "details": None,
        "occurred_at": NOW,
    }
    defaults.update(overrides)
    entry = AuditLog(**defaults)
    db.session.add(entry)
    db.session.commit()
    return entry


def test_list_audit_logs_orders_newest_first(client):
    oldest = _create_log(occurred_at=NOW - timedelta(hours=2))
    newest = _create_log(occurred_at=NOW)
    middle = _create_log(occurred_at=NOW - timedelta(hours=1))

    logs = list_audit_logs()

    assert [log.id for log in logs] == [newest.id, middle.id, oldest.id]


def test_list_audit_logs_respects_limit(client):
    entries = [_create_log(occurred_at=NOW - timedelta(hours=5 - i)) for i in range(5)]
    most_recent_three = entries[-3:]

    logs = list_audit_logs(limit=3)

    assert len(logs) == 3
    assert [log.id for log in logs] == [
        entry.id for entry in reversed(most_recent_three)
    ]


def test_route_rejects_unauthenticated_request(client):
    mark_installed()

    response = client.get("/reports-audit")

    assert_status(response, 401)


def test_route_rejects_non_auditor_role(client, login_as):
    login_as("REQUESTER")

    response = client.get("/reports-audit")

    assert_status(response, 403)


def test_auditor_sees_action_entity_and_details(client, login_as):
    login_as("AUDITOR")
    _create_log(
        action="booking.cancel",
        entity_type="booking",
        entity_id=42,
        details="cancelled by operator",
    )

    response = client.get("/reports-audit")

    assert_status(response, 200)
    body = response.get_data(as_text=True)
    assert "booking.cancel" in body
    assert "booking#42" in body
    assert "cancelled by operator" in body


def test_log_without_actor_renders_system(client, login_as):
    login_as("AUDITOR")
    _create_log(actor_id=None, action="no_show.auto")

    response = client.get("/reports-audit")

    assert_status(response, 200)
    assert "System" in response.get_data(as_text=True)


def test_log_with_actor_renders_display_name_not_username_or_id(client, login_as):
    login_as("AUDITOR")
    actor = _create_user(username="jane.doe", display_name="Jane Doe")
    _create_log(actor_id=actor.id, action="key.issue")

    response = client.get("/reports-audit")

    assert_status(response, 200)
    body = response.get_data(as_text=True)
    assert "Jane Doe" in body
    assert "jane.doe" not in body


def test_admin_can_also_reach_reports_audit(client, login_as):
    login_as("ADMIN")

    response = client.get("/reports-audit")

    assert_status(response, 200)


def test_empty_state_shows_fallback_text(client, login_as):
    login_as("AUDITOR")

    response = client.get("/reports-audit")

    assert_status(response, 200)
    assert "No audit log entries yet." in response.get_data(as_text=True)
