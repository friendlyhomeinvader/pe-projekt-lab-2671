import itertools
from datetime import datetime, timedelta, timezone

import pytest

from app import db
from app.models.audit_log import AuditLog
from app.models.booking import Booking
from app.models.issue_ticket import IssueTicket
from app.models.key import Key
from app.models.room import Room
from app.models.user import User
from app.services.issue_ticket import (
    create_issue_ticket,
    list_issue_tickets,
    resolve_issue_ticket,
)
from app.services.key_transaction import issue_key

_counter = itertools.count()

NOW = datetime.now(timezone.utc).replace(tzinfo=None)


def _create_room(**overrides):
    n = next(_counter)
    defaults = {"code": f"IT{n}", "location": "Building IT", "capacity": 10}
    defaults.update(overrides)
    room = Room(**defaults)
    db.session.add(room)
    db.session.commit()
    return room


def _create_key(room, **overrides):
    n = next(_counter)
    defaults = {"tag": f"IT-KEY-{n}", "is_master_key": False, "room_id": room.id}
    defaults.update(overrides)
    key = Key(**defaults)
    db.session.add(key)
    db.session.commit()
    return key


def _create_user(role, **overrides):
    n = next(_counter)
    defaults = {
        "username": f"it.{role.lower()}.{n}",
        "display_name": f"IT {role.title()} {n}",
        "email": f"it.{role.lower()}.{n}@uni.su",
        "role": role,
    }
    defaults.update(overrides)
    user = User(**defaults)
    user.set_password("Password123456!!")
    db.session.add(user)
    db.session.commit()
    return user


def _create_booking(requester, room, start_date=None, end_date=None, state="ACTIVE"):
    booking = Booking(
        start_date=start_date or (NOW - timedelta(hours=1)),
        end_date=end_date or (NOW + timedelta(hours=1)),
        state=state,
        requester_id=requester.id,
        room_id=room.id,
    )
    db.session.add(booking)
    db.session.commit()
    return booking


def _audit_rows(action):
    return AuditLog.query.filter_by(action=action).all()


def test_create_issue_ticket_succeeds_with_valid_description(client):
    room = _create_room()
    key = _create_key(room)
    reporter = _create_user("OPERATOR")

    ticket = create_issue_ticket(
        {
            "room_id": room.id,
            "key_id": key.id,
            "reported_by_id": reporter.id,
            "operator_id": reporter.id,
            "description": "Broken chair in the corner.",
        }
    )

    assert ticket.id is not None
    assert ticket.state == "OPEN"
    assert ticket.created_at is not None
    assert ticket.description == "Broken chair in the corner."


@pytest.mark.parametrize("description", ["", "   ", None])
def test_create_issue_ticket_raises_on_blank_description(client, description):
    room = _create_room()
    reporter = _create_user("OPERATOR")

    with pytest.raises(ValueError):
        create_issue_ticket(
            {
                "room_id": room.id,
                "reported_by_id": reporter.id,
                "operator_id": reporter.id,
                "description": description,
            }
        )


def test_resolve_issue_ticket_flips_state_and_sets_fields(client):
    room = _create_room()
    reporter = _create_user("OPERATOR")
    resolver = _create_user("OPERATOR")
    ticket = create_issue_ticket(
        {
            "room_id": room.id,
            "reported_by_id": reporter.id,
            "operator_id": reporter.id,
            "description": "Leaking tap.",
        }
    )

    resolve_issue_ticket(ticket, resolver.id)

    assert ticket.state == "RESOLVED"
    assert ticket.resolved_by_id == resolver.id
    assert ticket.resolved_at is not None


def test_resolve_issue_ticket_raises_if_already_resolved(client):
    room = _create_room()
    reporter = _create_user("OPERATOR")
    ticket = create_issue_ticket(
        {
            "room_id": room.id,
            "reported_by_id": reporter.id,
            "operator_id": reporter.id,
            "description": "Flickering lights.",
        }
    )
    resolve_issue_ticket(ticket, reporter.id)

    with pytest.raises(ValueError):
        resolve_issue_ticket(ticket, reporter.id)


def test_list_issue_tickets_orders_newest_first(client):
    room = _create_room()
    reporter = _create_user("OPERATOR")

    oldest = create_issue_ticket(
        {
            "room_id": room.id,
            "reported_by_id": reporter.id,
            "operator_id": reporter.id,
            "description": "First report.",
        }
    )
    oldest.created_at = NOW - timedelta(hours=2)
    middle = create_issue_ticket(
        {
            "room_id": room.id,
            "reported_by_id": reporter.id,
            "operator_id": reporter.id,
            "description": "Second report.",
        }
    )
    middle.created_at = NOW - timedelta(hours=1)
    newest = create_issue_ticket(
        {
            "room_id": room.id,
            "reported_by_id": reporter.id,
            "operator_id": reporter.id,
            "description": "Third report.",
        }
    )
    newest.created_at = NOW
    db.session.commit()

    result = list_issue_tickets()

    assert [t.id for t in result] == [newest.id, middle.id, oldest.id]


def test_key_issue_route_with_raise_ticket_creates_ticket_and_audit_row(
    client, login_as
):
    operator = login_as("OPERATOR")
    room = _create_room()
    key = _create_key(room)
    requester = _create_user("REQUESTER")

    response = client.post(
        f"/key-handling/keys/{key.id}/issue",
        data={
            "holder_id": str(requester.id),
            "identification_type": "PIN",
            "identification_value": "1234",
            "room_condition_notes": "Carpet is stained.",
            "raise_ticket": "on",
        },
    )

    assert response.status_code == 200
    tickets = IssueTicket.query.all()
    assert len(tickets) == 1
    ticket = tickets[0]
    assert ticket.key_id == key.id
    assert ticket.reported_by_id == operator.id
    assert ticket.operator_id == operator.id
    assert ticket.description == "Carpet is stained."
    assert len(_audit_rows("issue_ticket.create")) == 1


def test_key_return_route_with_raise_ticket_creates_ticket_and_audit_row(
    client, login_as
):
    operator = login_as("OPERATOR")
    room = _create_room()
    key = _create_key(room)
    requester = _create_user("REQUESTER")
    issue_key(
        key,
        identification_type="PIN",
        identification_value="1234",
        operator_id=operator.id,
        holder_id=requester.id,
    )

    response = client.post(
        f"/key-handling/keys/{key.id}/return",
        data={
            "identification_type": "PIN",
            "identification_value": "1234",
            "room_condition_notes": "Desk scratched.",
            "raise_ticket": "on",
        },
    )

    assert response.status_code == 200
    tickets = IssueTicket.query.all()
    assert len(tickets) == 1
    ticket = tickets[0]
    assert ticket.key_id == key.id
    assert ticket.reported_by_id == operator.id
    assert ticket.operator_id == operator.id
    assert ticket.description == "Desk scratched."
    assert len(_audit_rows("issue_ticket.create")) == 1


def test_booking_issue_route_with_raise_ticket_creates_ticket_and_audit_row(
    client, login_as
):
    operator = login_as("OPERATOR")
    room = _create_room()
    key = _create_key(room)
    requester = _create_user("REQUESTER")
    booking = _create_booking(requester, room, state="PENDING")

    response = client.post(
        f"/key-handling/bookings/{booking.id}/issue",
        data={
            "identification_type": "PIN",
            "identification_value": "1234",
            "room_condition_notes": "Projector flickers.",
            "raise_ticket": "on",
        },
    )

    assert response.status_code == 200
    tickets = IssueTicket.query.all()
    assert len(tickets) == 1
    ticket = tickets[0]
    assert ticket.key_id == key.id
    assert ticket.room_id == room.id
    assert ticket.reported_by_id == operator.id
    assert ticket.operator_id == operator.id
    assert ticket.description == "Projector flickers."
    assert len(_audit_rows("issue_ticket.create")) == 1


def test_booking_return_route_with_raise_ticket_creates_ticket_and_audit_row(
    client, login_as
):
    operator = login_as("OPERATOR")
    room = _create_room()
    key = _create_key(room)
    requester = _create_user("REQUESTER")
    booking = _create_booking(requester, room, state="PENDING")
    issue_key(
        key,
        identification_type="PIN",
        identification_value="1234",
        operator_id=operator.id,
        booking_id=booking.id,
    )

    response = client.post(
        f"/key-handling/bookings/{booking.id}/return",
        data={
            "identification_type": "PIN",
            "identification_value": "1234",
            "room_condition_notes": "Whiteboard marker dried out.",
            "raise_ticket": "on",
        },
    )

    assert response.status_code == 200
    tickets = IssueTicket.query.all()
    assert len(tickets) == 1
    ticket = tickets[0]
    assert ticket.key_id == key.id
    assert ticket.room_id == room.id
    assert ticket.reported_by_id == operator.id
    assert ticket.operator_id == operator.id
    assert ticket.description == "Whiteboard marker dried out."
    assert len(_audit_rows("issue_ticket.create")) == 1


def test_unchecked_raise_ticket_creates_no_ticket_and_no_audit_row(client, login_as):
    login_as("OPERATOR")
    room = _create_room()
    key = _create_key(room)
    requester = _create_user("REQUESTER")

    response = client.post(
        f"/key-handling/keys/{key.id}/issue",
        data={
            "holder_id": str(requester.id),
            "identification_type": "PIN",
            "identification_value": "1234",
            "room_condition_notes": "Should not matter.",
        },
    )

    assert response.status_code == 200
    assert IssueTicket.query.count() == 0
    assert len(_audit_rows("issue_ticket.create")) == 0


def test_blank_room_condition_notes_falls_back_to_default_description(client, login_as):
    login_as("OPERATOR")
    room = _create_room()
    key = _create_key(room)
    requester = _create_user("REQUESTER")

    response = client.post(
        f"/key-handling/keys/{key.id}/issue",
        data={
            "holder_id": str(requester.id),
            "identification_type": "PIN",
            "identification_value": "1234",
            "room_condition_notes": "   ",
            "raise_ticket": "on",
        },
    )

    assert response.status_code == 200
    tickets = IssueTicket.query.all()
    assert len(tickets) == 1
    assert tickets[0].description == "Reported during key handling."


def test_ticket_room_id_follows_booking_room_when_booking_tied(client, login_as):
    login_as("OPERATOR")
    key_own_room = _create_room()
    booking_room = _create_room()
    master_key = _create_key(key_own_room, is_master_key=True)
    master_key.rooms.append(booking_room)
    db.session.commit()
    requester = _create_user("REQUESTER")
    booking = _create_booking(requester, booking_room, state="PENDING")

    response = client.post(
        f"/key-handling/keys/{master_key.id}/issue",
        data={
            "identification_type": "PIN",
            "identification_value": "1234",
            "booking_id": str(booking.id),
            "room_condition_notes": "Window latch broken.",
            "raise_ticket": "on",
        },
    )

    assert response.status_code == 200
    tickets = IssueTicket.query.all()
    assert len(tickets) == 1
    assert tickets[0].room_id == booking_room.id
    assert tickets[0].room_id != key_own_room.id


def test_ticket_room_id_falls_back_to_key_room_when_no_booking(client, login_as):
    login_as("OPERATOR")
    room = _create_room()
    key = _create_key(room)
    requester = _create_user("REQUESTER")

    response = client.post(
        f"/key-handling/keys/{key.id}/issue",
        data={
            "holder_id": str(requester.id),
            "identification_type": "PIN",
            "identification_value": "1234",
            "room_condition_notes": "Blinds stuck.",
            "raise_ticket": "on",
        },
    )

    assert response.status_code == 200
    tickets = IssueTicket.query.all()
    assert len(tickets) == 1
    assert tickets[0].room_id == room.id


def test_damage_reported_alone_does_not_create_ticket(client, login_as):
    operator = login_as("OPERATOR")
    room = _create_room()
    key = _create_key(room)
    requester = _create_user("REQUESTER")
    issue_key(
        key,
        identification_type="PIN",
        identification_value="1234",
        operator_id=operator.id,
        holder_id=requester.id,
    )

    response = client.post(
        f"/key-handling/keys/{key.id}/return",
        data={
            "identification_type": "PIN",
            "identification_value": "1234",
            "room_condition_notes": "Minor scuff.",
            "damage_reported": "on",
        },
    )

    assert response.status_code == 200
    assert IssueTicket.query.count() == 0
    assert len(_audit_rows("issue_ticket.create")) == 0


def test_raise_ticket_alone_does_not_require_damage_reported(client, login_as):
    operator = login_as("OPERATOR")
    room = _create_room()
    key = _create_key(room)
    requester = _create_user("REQUESTER")
    transaction = issue_key(
        key,
        identification_type="PIN",
        identification_value="1234",
        operator_id=operator.id,
        holder_id=requester.id,
    )

    response = client.post(
        f"/key-handling/keys/{key.id}/return",
        data={
            "identification_type": "PIN",
            "identification_value": "1234",
            "room_condition_notes": "Nothing wrong, just reporting.",
            "raise_ticket": "on",
        },
    )

    assert response.status_code == 200
    assert IssueTicket.query.count() == 1
    db.session.refresh(transaction)
    assert transaction.damage_reported is False
