import itertools
import re
from datetime import datetime, timezone

import pytest

from app import db
from app.models.audit_log import AuditLog
from app.models.maintenance_slot import MaintenanceSlot
from app.models.room import Room
from app.models.user import User
from app.services.issue_ticket import (
    create_issue_ticket,
    mark_issue_ticket_in_progress,
    resolve_issue_ticket,
)
from app.services.maintenance import create_maintenance_slot
from app.services.preferences import mark_installed
from tests.helpers import assert_status

_counter = itertools.count()

START = datetime(2027, 3, 1, 9, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None)
END = datetime(2027, 3, 2, 9, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None)

GATED_ROUTES = [
    ("get", "/issue-management", False),
    ("get", "/issue-tickets", True),
    ("get", "/issue-tickets/1/resolve/confirm", True),
    ("post", "/issue-tickets/1/resolve", False),
    ("get", "/issue-tickets/1/convert/form", True),
    ("post", "/issue-tickets/1/convert", False),
]


def _create_room(**overrides):
    n = next(_counter)
    defaults = {"code": f"IM{n}", "location": "Building IM", "capacity": 10}
    defaults.update(overrides)
    room = Room(**defaults)
    db.session.add(room)
    db.session.commit()
    return room


def _create_user(role, **overrides):
    n = next(_counter)
    defaults = {
        "username": f"im.{role.lower()}.{n}",
        "display_name": f"IM {role.title()} {n}",
        "email": f"im.{role.lower()}.{n}@uni.su",
        "role": role,
    }
    defaults.update(overrides)
    user = User(**defaults)
    user.set_password("Password123456!!")
    db.session.add(user)
    db.session.commit()
    return user


def _create_ticket(room=None, **overrides):
    reporter = _create_user("OPERATOR")
    data = {
        "room_id": room.id if room else None,
        "reported_by_id": reporter.id,
        "operator_id": reporter.id,
        "description": "Broken chair.",
    }
    data.update(overrides)
    return create_issue_ticket(data)


def _audit_rows(action):
    return AuditLog.query.filter_by(action=action).all()


def _hx_headers(needs_hx):
    return {"HX-Request": "true"} if needs_hx else {}


def _has_resolve_action(body):
    return re.search(r">\s*Resolve\s*<", body) is not None


@pytest.mark.parametrize("method,path,needs_hx", GATED_ROUTES)
def test_unauthenticated_returns_401(client, method, path, needs_hx):
    mark_installed()

    response = getattr(client, method)(path, headers=_hx_headers(needs_hx))

    assert_status(response, 401)


@pytest.mark.parametrize("method,path,needs_hx", GATED_ROUTES)
@pytest.mark.parametrize("role", ["OPERATOR", "REQUESTER"])
def test_non_admin_returns_403(client, login_as, method, path, needs_hx, role):
    login_as(role)

    response = getattr(client, method)(path, headers=_hx_headers(needs_hx))

    assert_status(response, 403)


def test_issue_management_page_admin_returns_200(client, login_as):
    login_as("ADMIN")

    response = client.get("/issue-management")

    assert_status(response, 200)


def test_issue_tickets_fragment_admin_returns_200(client, login_as):
    login_as("ADMIN")

    response = client.get("/issue-tickets", headers={"HX-Request": "true"})

    assert_status(response, 200)


def test_issue_management_page_shows_ticket_without_second_request(client, login_as):
    login_as("ADMIN")
    room = _create_room()
    _create_ticket(room, description="Leaky faucet in the corner.")

    response = client.get("/issue-management")

    assert_status(response, 200)
    body = response.get_data(as_text=True)
    assert "Leaky faucet in the corner." in body
    assert "Open" in body


def test_resolve_confirm_renders_ticket_description(client, login_as):
    login_as("ADMIN")
    room = _create_room()
    ticket = _create_ticket(room, description="Door lock stuck.")

    response = client.get(
        f"/issue-tickets/{ticket.id}/resolve/confirm", headers={"HX-Request": "true"}
    )

    assert_status(response, 200)
    assert "Door lock stuck." in response.get_data(as_text=True)


def test_resolve_post_resolves_ticket_and_writes_one_audit_row(client, login_as):
    admin = login_as("ADMIN")
    room = _create_room()
    ticket = _create_ticket(room, description="Window won't close.")

    response = client.post(f"/issue-tickets/{ticket.id}/resolve")

    assert_status(response, 200)
    db.session.refresh(ticket)
    assert ticket.state == "RESOLVED"
    assert ticket.resolved_by_id == admin.id
    assert ticket.resolved_at is not None

    logs = _audit_rows("issue_ticket.resolve")
    assert len(logs) == 1
    assert logs[0].entity_type == "issue_ticket"
    assert logs[0].entity_id == ticket.id
    assert logs[0].actor_id == admin.id


def test_resolve_twice_returns_422_without_second_audit_row_or_timestamp_change(
    client, login_as
):
    login_as("ADMIN")
    room = _create_room()
    ticket = _create_ticket(room, description="Broken blinds.")

    first = client.post(f"/issue-tickets/{ticket.id}/resolve")
    assert_status(first, 200)
    db.session.refresh(ticket)
    first_resolved_at = ticket.resolved_at

    second = client.post(f"/issue-tickets/{ticket.id}/resolve")

    assert_status(second, 422)
    db.session.refresh(ticket)
    assert ticket.resolved_at == first_resolved_at
    assert len(_audit_rows("issue_ticket.resolve")) == 1


def test_convert_form_404s_for_ticket_without_room(client, login_as):
    login_as("ADMIN")
    ticket = _create_ticket(room=None, description="No room ticket.")

    response = client.get(
        f"/issue-tickets/{ticket.id}/convert/form", headers={"HX-Request": "true"}
    )

    assert_status(response, 404)


def test_convert_form_renders_ticket_room_as_fixed_hidden_field(client, login_as):
    login_as("ADMIN")
    room = _create_room()
    ticket = _create_ticket(room, description="Flickering light.")

    response = client.get(
        f"/issue-tickets/{ticket.id}/convert/form", headers={"HX-Request": "true"}
    )

    assert_status(response, 200)
    body = response.get_data(as_text=True)
    assert f'name="room_id" value="{room.id}"' in body
    assert room.code in body


def test_convert_post_creates_slot_marks_in_progress_and_writes_two_audit_rows(
    client, login_as
):
    admin = login_as("ADMIN")
    room = _create_room()
    ticket = _create_ticket(room, description="Flickering light.")

    response = client.post(
        f"/issue-tickets/{ticket.id}/convert",
        data={
            "room_id": str(room.id),
            "start_date": START.isoformat(),
            "end_date": END.isoformat(),
            "reason": "Electrical repair",
        },
    )

    assert_status(response, 200)
    db.session.refresh(ticket)
    assert ticket.state == "IN_PROGRESS"

    slots = MaintenanceSlot.query.all()
    assert len(slots) == 1
    slot = slots[0]
    assert slot.room_id == room.id

    create_logs = _audit_rows("maintenance_slot.create")
    convert_logs = _audit_rows("issue_ticket.convert_to_maintenance")
    assert len(create_logs) == 1
    assert create_logs[0].entity_id == slot.id
    assert create_logs[0].actor_id == admin.id
    assert len(convert_logs) == 1
    assert convert_logs[0].entity_type == "issue_ticket"
    assert convert_logs[0].entity_id == ticket.id
    assert convert_logs[0].actor_id == admin.id
    assert str(slot.id) in convert_logs[0].details


def test_convert_post_invalid_dates_rerenders_form_with_error_and_makes_no_changes(
    client, login_as
):
    login_as("ADMIN")
    room = _create_room()
    ticket = _create_ticket(room, description="Broken window.")

    response = client.post(
        f"/issue-tickets/{ticket.id}/convert",
        data={
            "room_id": str(room.id),
            "start_date": END.isoformat(),
            "end_date": START.isoformat(),
            "reason": "Window repair",
        },
    )

    assert_status(response, 422)
    assert "end_date must be after start_date" in response.get_data(as_text=True)
    db.session.refresh(ticket)
    assert ticket.state == "OPEN"
    assert MaintenanceSlot.query.count() == 0
    assert AuditLog.query.count() == 0


def test_open_ticket_with_room_shows_both_resolve_and_convert_actions(client, login_as):
    login_as("ADMIN")
    room = _create_room()
    _create_ticket(room, description="Open with room.")

    response = client.get("/issue-tickets", headers={"HX-Request": "true"})

    assert_status(response, 200)
    body = response.get_data(as_text=True)
    assert "Open" in body
    assert _has_resolve_action(body)
    assert "Convert to maintenance" in body


def test_resolved_ticket_shows_neither_action(client, login_as):
    login_as("ADMIN")
    room = _create_room()
    ticket = _create_ticket(room, description="Already fixed leak.")
    resolve_issue_ticket(ticket, _create_user("OPERATOR").id)

    response = client.get("/issue-tickets", headers={"HX-Request": "true"})

    assert_status(response, 200)
    body = response.get_data(as_text=True)
    assert "Resolved" in body
    assert not _has_resolve_action(body)
    assert "Convert to maintenance" not in body


def test_in_progress_ticket_shows_resolve_but_not_convert(client, login_as):
    login_as("ADMIN")
    room = _create_room()
    ticket = _create_ticket(room, description="In progress ticket.")
    mark_issue_ticket_in_progress(ticket)

    response = client.get("/issue-tickets", headers={"HX-Request": "true"})

    assert_status(response, 200)
    body = response.get_data(as_text=True)
    assert "In progress" in body
    assert _has_resolve_action(body)
    assert "Convert to maintenance" not in body


def test_open_ticket_without_room_shows_resolve_but_not_convert(client, login_as):
    login_as("ADMIN")
    _create_ticket(room=None, description="Roomless ticket.")

    response = client.get("/issue-tickets", headers={"HX-Request": "true"})

    assert_status(response, 200)
    body = response.get_data(as_text=True)
    assert _has_resolve_action(body)
    assert "Convert to maintenance" not in body


def test_maintenance_create_success_oob_swaps_list_and_closes_modal_toggle(
    client, login_as
):
    login_as("ADMIN")
    room = _create_room()

    response = client.post(
        "/maintenance-slots",
        data={
            "room_id": str(room.id),
            "start_date": START.isoformat(),
            "end_date": END.isoformat(),
        },
    )

    assert_status(response, 200)
    body = response.get_data(as_text=True)
    assert 'hx-swap-oob="innerHTML:#issue-mgmt-content"' in body
    assert 'id="modal-toggle"' in body
    assert 'id="confirm-toggle"' not in body


def test_maintenance_delete_success_has_no_oob_wrapper_and_closes_confirm_toggle(
    client, login_as
):
    admin = login_as("ADMIN")
    room = _create_room()
    slot = create_maintenance_slot(
        {
            "room_id": room.id,
            "start_date": START,
            "end_date": END,
            "created_by_id": admin.id,
        }
    )

    response = client.delete(f"/maintenance-slots/{slot.id}")

    assert_status(response, 200)
    body = response.get_data(as_text=True)
    assert 'hx-swap-oob="innerHTML:#issue-mgmt-content"' not in body
    assert 'id="confirm-toggle"' in body
    assert 'id="modal-toggle"' not in body


def test_room_management_page_no_longer_has_maintenance_tab(client, login_as):
    login_as("ADMIN")

    response = client.get("/room-management")

    assert_status(response, 200)
    body = response.get_data(as_text=True)
    assert "Maintenance" not in body
    assert "Rooms</label>" in body
    assert "Features</label>" in body


def test_room_management_rooms_and_features_tabs_still_render(client, login_as):
    login_as("ADMIN")

    rooms_response = client.get("/rooms", headers={"HX-Request": "true"})
    features_response = client.get("/features", headers={"HX-Request": "true"})

    assert_status(rooms_response, 200)
    assert_status(features_response, 200)
