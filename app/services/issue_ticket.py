from datetime import datetime, timezone

from app import db
from app.models.issue_ticket import IssueTicket


def list_issue_tickets():
    return IssueTicket.query.order_by(IssueTicket.created_at.desc()).all()


def get_issue_ticket(ticket_id):
    return db.session.get(IssueTicket, ticket_id)


def create_issue_ticket(data):
    description = (data.get("description") or "").strip()
    if not description:
        raise ValueError("description is required.")

    ticket = IssueTicket(
        room_id=data.get("room_id"),
        key_id=data.get("key_id"),
        reported_by_id=data["reported_by_id"],
        operator_id=data["operator_id"],
        description=description,
        state="OPEN",
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.session.add(ticket)
    db.session.commit()
    return ticket


def resolve_issue_ticket(ticket, resolved_by_id):
    if ticket.state == "RESOLVED":
        raise ValueError("Ticket is already resolved.")
    ticket.state = "RESOLVED"
    ticket.resolved_by_id = resolved_by_id
    ticket.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    return ticket
