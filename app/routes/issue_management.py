from flask import abort, render_template, request
from flask_login import current_user
from marshmallow import ValidationError

from app.schemas.maintenance_slot import MaintenanceSlotIn
from app.services.audit import log_action
from app.services.auth import role_required
from app.services.issue_ticket import (
    ISSUE_TICKET_STATE_LABELS,
    ISSUE_TICKET_STATE_STYLES,
    get_issue_ticket,
    list_issue_tickets,
    mark_issue_ticket_in_progress,
    resolve_issue_ticket,
)
from app.services.maintenance import create_maintenance_slot
from app.services.nav import grouped_visible_nav_items
from app.services.notify import render_toast
from app.services.page import htmx_only, render_page


def _render_tickets_list():
    return render_template(
        "partials/issue_tickets/list.html",
        tickets=list_issue_tickets(),
        state_labels=ISSUE_TICKET_STATE_LABELS,
        state_styles=ISSUE_TICKET_STATE_STYLES,
    )


def _render_convert_form(*, ticket, values, errors, status=200):
    html = render_template(
        "partials/issue_tickets/convert_form.html",
        ticket=ticket,
        values=values,
        errors=errors,
    )
    return (html, status) if status != 200 else html


def register_issue_management_routes(app):
    @app.get("/issue-management")
    @role_required("ADMIN")
    def issue_management_page():
        return render_page(
            "partials/issue_management.html",
            nav_groups=grouped_visible_nav_items(current_user.role),
            title="Issue Mgmt",
            tickets=list_issue_tickets(),
            state_labels=ISSUE_TICKET_STATE_LABELS,
            state_styles=ISSUE_TICKET_STATE_STYLES,
        )

    @app.get("/issue-tickets")
    @htmx_only
    @role_required("ADMIN")
    def issue_tickets_list():
        return _render_tickets_list()

    @app.get("/issue-tickets/<int:ticket_id>/resolve/confirm")
    @htmx_only
    @role_required("ADMIN")
    def issue_tickets_resolve_confirm(ticket_id):
        ticket = get_issue_ticket(ticket_id)
        if ticket is None:
            abort(404)
        return render_template(
            "partials/issue_tickets/resolve_confirm.html", ticket=ticket
        )

    @app.post("/issue-tickets/<int:ticket_id>/resolve")
    @role_required("ADMIN")
    def issue_tickets_resolve(ticket_id):
        ticket = get_issue_ticket(ticket_id)
        if ticket is None:
            abort(404)

        try:
            resolve_issue_ticket(ticket, current_user.id)
        except ValueError as err:
            return _render_tickets_list() + render_toast("error", str(err)), 422

        log_action(
            current_user.id,
            "issue_ticket.resolve",
            entity_type="issue_ticket",
            entity_id=ticket.id,
        )
        return render_template(
            "partials/issue_tickets/resolve_success.html",
            tickets=list_issue_tickets(),
            state_labels=ISSUE_TICKET_STATE_LABELS,
            state_styles=ISSUE_TICKET_STATE_STYLES,
        ) + render_toast("success", "Issue ticket resolved.")

    @app.get("/issue-tickets/<int:ticket_id>/convert/form")
    @htmx_only
    @role_required("ADMIN")
    def issue_tickets_convert_form(ticket_id):
        ticket = get_issue_ticket(ticket_id)
        if ticket is None or ticket.room_id is None:
            abort(404)
        return _render_convert_form(
            ticket=ticket,
            values={"reason": ticket.description},
            errors={},
        )

    @app.post("/issue-tickets/<int:ticket_id>/convert")
    @role_required("ADMIN")
    def issue_tickets_convert(ticket_id):
        ticket = get_issue_ticket(ticket_id)
        if ticket is None or ticket.room_id is None:
            abort(404)

        try:
            data = MaintenanceSlotIn().load(request.form)
        except ValidationError as err:
            return _render_convert_form(
                ticket=ticket, values=request.form, errors=err.messages, status=422
            )

        data["created_by_id"] = current_user.id
        try:
            slot = create_maintenance_slot(data)
        except ValueError as err:
            return _render_convert_form(
                ticket=ticket,
                values=request.form,
                errors={"end_date": [str(err)]},
                status=422,
            )

        mark_issue_ticket_in_progress(ticket)

        log_action(
            current_user.id,
            "maintenance_slot.create",
            entity_type="maintenance_slot",
            entity_id=slot.id,
            details=f"room={slot.room.code}",
        )
        log_action(
            current_user.id,
            "issue_ticket.convert_to_maintenance",
            entity_type="issue_ticket",
            entity_id=ticket.id,
            details=f"maintenance_slot={slot.id}",
        )
        return render_template(
            "partials/issue_tickets/convert_success.html",
            tickets=list_issue_tickets(),
            state_labels=ISSUE_TICKET_STATE_LABELS,
            state_styles=ISSUE_TICKET_STATE_STYLES,
        ) + render_toast(
            "success", f"Converted to a maintenance slot for {slot.room.code}."
        )
