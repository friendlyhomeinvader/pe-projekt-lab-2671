from flask import abort, render_template, request
from flask_login import current_user
from marshmallow import ValidationError

from app.schemas.maintenance_slot import MaintenanceSlotIn
from app.services.audit import log_action
from app.services.auth import role_required
from app.services.booking import BOOKING_STATE_LABELS, BOOKING_STATE_STYLES
from app.services.maintenance import (
    MaintenanceSlotConflict,
    create_maintenance_slot,
    delete_maintenance_slot,
    get_maintenance_slot,
    list_maintenance_slots,
    update_maintenance_slot,
)
from app.services.notify import render_toast
from app.services.page import htmx_only
from app.services.room import list_rooms


def _field_for_maintenance_error(err):
    return "room_id" if "room" in str(err).lower() else "end_date"


def _render_maintenance_slot_form(*, is_edit, values, errors, slot_id=None, status=200):
    kwargs = {
        "is_edit": is_edit,
        "values": values,
        "errors": errors,
        "rooms": list_rooms(),
    }
    if slot_id is not None:
        kwargs["slot_id"] = slot_id
    html = render_template("partials/maintenance/form.html", **kwargs)
    return (html, status) if status != 200 else html


def _maintenance_slot_save_success(slot, verb):
    return render_template(
        "partials/maintenance/save_success.html", slots=list_maintenance_slots()
    ) + render_toast("success", f"Maintenance slot for {slot.room.code} {verb}.")


def _render_conflict_confirm(*, is_edit, values, bookings, slot_id=None):
    kwargs = {
        "is_edit": is_edit,
        "values": values,
        "bookings": bookings,
        "state_labels": BOOKING_STATE_LABELS,
        "state_styles": BOOKING_STATE_STYLES,
    }
    if slot_id is not None:
        kwargs["slot_id"] = slot_id
    return render_template("partials/maintenance/conflict_confirm.html", **kwargs)


def register_maintenance_routes(app):
    @app.get("/maintenance-slots")
    @htmx_only
    @role_required("ADMIN")
    def maintenance_slots_list():
        return render_template(
            "partials/maintenance/list.html", slots=list_maintenance_slots()
        )

    @app.get("/maintenance-slots/new")
    @htmx_only
    @role_required("ADMIN")
    def maintenance_slots_new():
        return _render_maintenance_slot_form(is_edit=False, values={}, errors={})

    @app.get("/maintenance-slots/<int:slot_id>/edit")
    @htmx_only
    @role_required("ADMIN")
    def maintenance_slots_edit(slot_id):
        slot = get_maintenance_slot(slot_id)
        if slot is None:
            abort(404)
        values = {
            "room_id": slot.room_id,
            "start_date": slot.start_date.isoformat(timespec="minutes"),
            "end_date": slot.end_date.isoformat(timespec="minutes"),
            "reason": slot.reason,
        }
        return _render_maintenance_slot_form(
            is_edit=True, slot_id=slot.id, values=values, errors={}
        )

    @app.post("/maintenance-slots")
    @role_required("ADMIN")
    def maintenance_slots_create():
        try:
            data = MaintenanceSlotIn().load(request.form)
        except ValidationError as err:
            return _render_maintenance_slot_form(
                is_edit=False, values=request.form, errors=err.messages, status=422
            )

        data["created_by_id"] = current_user.id
        try:
            slot = create_maintenance_slot(data)
        except MaintenanceSlotConflict as err:
            return _render_conflict_confirm(
                is_edit=False, values=request.form, bookings=err.bookings
            )
        except ValueError as err:
            return _render_maintenance_slot_form(
                is_edit=False,
                values=request.form,
                errors={_field_for_maintenance_error(err): [str(err)]},
                status=422,
            )

        details = f"room={slot.room.code}"
        if slot.overridden_conflicts:
            ids = ", ".join(f"#{b.id}" for b in slot.overridden_conflicts)
            details += f", overrode {len(slot.overridden_conflicts)} conflicting booking(s): {ids}"
        log_action(
            current_user.id,
            "maintenance_slot.create",
            entity_type="maintenance_slot",
            entity_id=slot.id,
            details=details,
        )
        return _maintenance_slot_save_success(slot, "created")

    @app.patch("/maintenance-slots/<int:slot_id>")
    @role_required("ADMIN")
    def maintenance_slots_update(slot_id):
        slot = get_maintenance_slot(slot_id)
        if slot is None:
            abort(404)

        try:
            data = MaintenanceSlotIn(partial=True).load(request.form)
        except ValidationError as err:
            return _render_maintenance_slot_form(
                is_edit=True,
                slot_id=slot_id,
                values=request.form,
                errors=err.messages,
                status=422,
            )

        try:
            slot = update_maintenance_slot(slot, data)
        except MaintenanceSlotConflict as err:
            return _render_conflict_confirm(
                is_edit=True,
                slot_id=slot_id,
                values=request.form,
                bookings=err.bookings,
            )
        except ValueError as err:
            return _render_maintenance_slot_form(
                is_edit=True,
                slot_id=slot_id,
                values=request.form,
                errors={_field_for_maintenance_error(err): [str(err)]},
                status=422,
            )

        details = f"room={slot.room.code}"
        if slot.overridden_conflicts:
            ids = ", ".join(f"#{b.id}" for b in slot.overridden_conflicts)
            details += f", overrode {len(slot.overridden_conflicts)} conflicting booking(s): {ids}"
        log_action(
            current_user.id,
            "maintenance_slot.update",
            entity_type="maintenance_slot",
            entity_id=slot.id,
            details=details,
        )
        return _maintenance_slot_save_success(slot, "updated")

    @app.get("/maintenance-slots/<int:slot_id>/delete/confirm")
    @htmx_only
    @role_required("ADMIN")
    def maintenance_slots_delete_confirm(slot_id):
        slot = get_maintenance_slot(slot_id)
        if slot is None:
            abort(404)
        return render_template("partials/maintenance/delete_confirm.html", slot=slot)

    @app.delete("/maintenance-slots/<int:slot_id>")
    @role_required("ADMIN")
    def maintenance_slots_delete(slot_id):
        slot = get_maintenance_slot(slot_id)
        if slot is None:
            abort(404)
        slot_id_value = slot.id
        room_code = slot.room.code
        delete_maintenance_slot(slot)
        log_action(
            current_user.id,
            "maintenance_slot.delete",
            entity_type="maintenance_slot",
            entity_id=slot_id_value,
            details=f"room={room_code}",
        )
        return render_template(
            "partials/maintenance/delete_success.html", slots=list_maintenance_slots()
        ) + render_toast("success", f"Maintenance slot for {room_code} deleted.")
