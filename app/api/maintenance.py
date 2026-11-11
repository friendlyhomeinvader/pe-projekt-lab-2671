from apiflask import APIBlueprint, EmptySchema, abort
from flask_login import current_user

from app.schemas.maintenance_slot import MaintenanceSlotIn, MaintenanceSlotOut
from app.services.audit import log_action
from app.services.auth import role_required
from app.services.maintenance import (
    create_maintenance_slot,
    delete_maintenance_slot,
    get_maintenance_slot,
    list_maintenance_slots,
    update_maintenance_slot,
)

maintenance_slots_blp = APIBlueprint(
    "maintenance_slots",
    __name__,
    url_prefix="/api/maintenance-slots",
    tag="Maintenance Slots",
)


@maintenance_slots_blp.get("/")
@maintenance_slots_blp.output(MaintenanceSlotOut(many=True))
def get_maintenance_slots():
    return list_maintenance_slots()


@maintenance_slots_blp.post("/")
@maintenance_slots_blp.input(MaintenanceSlotIn)
@maintenance_slots_blp.output(MaintenanceSlotOut, status_code=201)
@role_required("ADMIN")
def create_maintenance_slot_view(json_data):
    json_data["created_by_id"] = current_user.id
    try:
        slot = create_maintenance_slot(json_data)
    except ValueError as err:
        abort(422, message=str(err))
    log_action(
        current_user.id,
        "maintenance_slot.create",
        entity_type="maintenance_slot",
        entity_id=slot.id,
        details=f"room={slot.room.code}",
    )
    return slot


@maintenance_slots_blp.get("/<int:slot_id>/")
@maintenance_slots_blp.output(MaintenanceSlotOut)
def get_maintenance_slot_view(slot_id):
    slot = get_maintenance_slot(slot_id)
    if slot is None:
        abort(404, message="Maintenance slot not found.")
    return slot


@maintenance_slots_blp.patch("/<int:slot_id>/")
@maintenance_slots_blp.input(MaintenanceSlotIn(partial=True))
@maintenance_slots_blp.output(MaintenanceSlotOut)
@role_required("ADMIN")
def update_maintenance_slot_view(slot_id, json_data):
    slot = get_maintenance_slot(slot_id)
    if slot is None:
        abort(404, message="Maintenance slot not found.")
    try:
        slot = update_maintenance_slot(slot, json_data)
    except ValueError as err:
        abort(422, message=str(err))
    log_action(
        current_user.id,
        "maintenance_slot.update",
        entity_type="maintenance_slot",
        entity_id=slot.id,
        details=f"room={slot.room.code}",
    )
    return slot


@maintenance_slots_blp.delete("/<int:slot_id>/")
@maintenance_slots_blp.output(EmptySchema, status_code=204)
@role_required("ADMIN")
def delete_maintenance_slot_view(slot_id):
    slot = get_maintenance_slot(slot_id)
    if slot is None:
        abort(404, message="Maintenance slot not found.")
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
