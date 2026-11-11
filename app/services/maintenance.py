from datetime import datetime, timezone

from app.models.maintenance_slot import MaintenanceSlot


def rooms_under_maintenance(room_ids, now=None):
    room_ids = list(room_ids)
    if not room_ids:
        return set()
    if now is None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = MaintenanceSlot.query.filter(
        MaintenanceSlot.room_id.in_(room_ids),
        MaintenanceSlot.start_date <= now,
        MaintenanceSlot.end_date >= now,
    ).all()
    return {row.room_id for row in rows}
