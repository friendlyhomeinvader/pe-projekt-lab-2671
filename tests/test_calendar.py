from datetime import datetime, timedelta, timezone

from app import db
from app.models.room import Room
from app.models.user import User
from app.services.booking import create_booking
from app.services.calendar import build_week_view
from app.services.maintenance import create_maintenance_slot

MONDAY_9AM = datetime(2027, 3, 1, 9, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None)


def _create_room(**overrides):
    defaults = {"code": "CAL1", "location": "Building C", "capacity": 10}
    defaults.update(overrides)
    room = Room(**defaults)
    db.session.add(room)
    db.session.commit()
    return room


def _create_admin():
    user = User(
        username="calendar.admin",
        display_name="Calendar Admin",
        email="calendar.admin@uni.su",
        role="ADMIN",
    )
    user.set_password("Password123456!!")
    db.session.add(user)
    db.session.commit()
    return user


def _create_requester():
    user = User(
        username="calendar.requester",
        display_name="Calendar Requester",
        email="calendar.requester@uni.su",
        role="REQUESTER",
    )
    user.set_password("Password123456!!")
    db.session.add(user)
    db.session.commit()
    return user


def _week_offset_for(target_date, today):
    target_monday = target_date - timedelta(days=target_date.weekday())
    this_monday = today - timedelta(days=today.weekday())
    return (target_monday - this_monday).days // 7


def test_build_week_view_shows_maintenance_block(client):
    admin = _create_admin()
    room = _create_room()
    create_maintenance_slot(
        {
            "room_id": room.id,
            "start_date": MONDAY_9AM,
            "end_date": MONDAY_9AM + timedelta(hours=2),
            "reason": "Rewiring",
            "created_by_id": admin.id,
        }
    )
    week_offset = _week_offset_for(MONDAY_9AM.date(), datetime.now(timezone.utc).date())

    view = build_week_view(room.id, week_offset, admin.id)

    day = next(d for d in view["days"] if d["date"] == MONDAY_9AM.date())
    assert len(day["maintenance"]) == 1
    assert "Under maintenance" in day["maintenance"][0]["label"]
    assert "Rewiring" in day["maintenance"][0]["label"]
    assert day["bookings"] == []


def test_build_week_view_maintenance_blocks_clickable_slot(client):
    admin = _create_admin()
    room = _create_room()
    create_maintenance_slot(
        {
            "room_id": room.id,
            "start_date": MONDAY_9AM,
            "end_date": MONDAY_9AM + timedelta(hours=11),
            "created_by_id": admin.id,
        }
    )
    week_offset = _week_offset_for(MONDAY_9AM.date(), datetime.now(timezone.utc).date())

    view = build_week_view(room.id, week_offset, admin.id)

    day = next(d for d in view["days"] if d["date"] == MONDAY_9AM.date())
    for block in day["clickable"]:
        row_start = datetime.fromisoformat(block["row_start_iso"])
        row_end = datetime.fromisoformat(block["row_end_iso"])
        assert row_end <= MONDAY_9AM or row_start >= MONDAY_9AM + timedelta(hours=11)


def test_create_booking_rejected_when_room_under_maintenance(client):
    admin = _create_admin()
    requester = _create_requester()
    room = _create_room()
    create_maintenance_slot(
        {
            "room_id": room.id,
            "start_date": MONDAY_9AM,
            "end_date": MONDAY_9AM + timedelta(hours=2),
            "created_by_id": admin.id,
        }
    )

    try:
        create_booking(
            {
                "start_date": MONDAY_9AM + timedelta(minutes=30),
                "end_date": MONDAY_9AM + timedelta(hours=1),
                "state": "PENDING",
                "requester_id": requester.id,
                "room_id": room.id,
            }
        )
        raised = False
    except ValueError as err:
        raised = True
        assert "maintenance" in str(err)

    assert raised
