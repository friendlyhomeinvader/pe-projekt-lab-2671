import itertools
from datetime import datetime, timedelta, timezone

import pytest

from app import db
from app.models.audit_log import AuditLog
from app.models.room import Room
from app.models.user import User
from app.services.maintenance import (
    create_maintenance_slot,
    delete_maintenance_slot,
    get_maintenance_slot,
    list_maintenance_slots,
    update_maintenance_slot,
)
from app.services.preferences import mark_installed
from tests.helpers import assert_status

_room_counter = itertools.count()

START = datetime(2027, 1, 1, 9, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None)
END = datetime(2027, 1, 2, 9, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None)


def _create_room(**overrides):
    n = next(_room_counter)
    defaults = {
        "code": f"M{n}",
        "location": "Building M",
        "capacity": 10,
    }
    defaults.update(overrides)
    room = Room(**defaults)
    db.session.add(room)
    db.session.commit()
    return room


def _create_admin():
    n = next(_room_counter)
    user = User(
        username=f"maintenance.admin.{n}",
        display_name=f"Maintenance Admin {n}",
        email=f"maintenance.admin.{n}@uni.su",
        role="ADMIN",
    )
    user.set_password("Password123456!!")
    db.session.add(user)
    db.session.commit()
    return user


def _slot_data(room_id, **overrides):
    payload = {
        "room_id": room_id,
        "start_date": START,
        "end_date": END,
        "created_by_id": None,
    }
    payload.update(overrides)
    return payload


def _form_payload(room_id, **overrides):
    payload = {
        "room_id": str(room_id),
        "start_date": START.isoformat(),
        "end_date": END.isoformat(),
    }
    payload.update(overrides)
    return payload


def test_create_maintenance_slot_succeeds_with_valid_data(client, login_as):
    admin = login_as("ADMIN")
    room = _create_room()

    slot = create_maintenance_slot(_slot_data(room.id, created_by_id=admin.id))

    assert slot.id is not None
    assert slot.room_id == room.id
    assert slot.start_date == START
    assert slot.end_date == END
    assert slot.created_by_id == admin.id


def test_create_maintenance_slot_unknown_room_raises(client):
    admin = _create_admin()

    with pytest.raises(ValueError):
        create_maintenance_slot(_slot_data(999999, created_by_id=admin.id))


def test_create_maintenance_slot_invalid_dates_raises(client):
    admin = _create_admin()
    room = _create_room()

    with pytest.raises(ValueError):
        create_maintenance_slot(
            _slot_data(room.id, start_date=END, end_date=START, created_by_id=admin.id)
        )


def test_create_maintenance_slot_equal_dates_raises(client):
    admin = _create_admin()
    room = _create_room()

    with pytest.raises(ValueError):
        create_maintenance_slot(
            _slot_data(
                room.id, start_date=START, end_date=START, created_by_id=admin.id
            )
        )


def test_update_maintenance_slot_unknown_room_raises(client):
    admin = _create_admin()
    room = _create_room()
    slot = create_maintenance_slot(_slot_data(room.id, created_by_id=admin.id))

    with pytest.raises(ValueError):
        update_maintenance_slot(slot, {"room_id": 999999})


def test_update_maintenance_slot_partial_end_date_before_existing_start_raises(client):
    admin = _create_admin()
    room = _create_room()
    slot = create_maintenance_slot(_slot_data(room.id, created_by_id=admin.id))

    with pytest.raises(ValueError):
        update_maintenance_slot(slot, {"end_date": START - timedelta(days=1)})

    assert get_maintenance_slot(slot.id).end_date == END


def test_update_maintenance_slot_applies_valid_partial_change(client):
    admin = _create_admin()
    room = _create_room()
    slot = create_maintenance_slot(_slot_data(room.id, created_by_id=admin.id))

    updated = update_maintenance_slot(slot, {"reason": "Rewiring"})

    assert updated.reason == "Rewiring"
    assert updated.start_date == START
    assert updated.end_date == END


def test_delete_maintenance_slot_removes_row(client):
    admin = _create_admin()
    room = _create_room()
    slot = create_maintenance_slot(_slot_data(room.id, created_by_id=admin.id))
    slot_id = slot.id

    delete_maintenance_slot(slot)

    assert get_maintenance_slot(slot_id) is None


def test_list_maintenance_slots_orders_by_start_date(client):
    admin = _create_admin()
    room = _create_room()
    later = create_maintenance_slot(
        _slot_data(
            room.id,
            start_date=START + timedelta(days=10),
            end_date=END + timedelta(days=10),
            created_by_id=admin.id,
        )
    )
    earlier = create_maintenance_slot(
        _slot_data(
            room.id,
            start_date=START - timedelta(days=10),
            end_date=END - timedelta(days=10),
            created_by_id=admin.id,
        )
    )

    slots = list_maintenance_slots()

    assert [slot.id for slot in slots] == [earlier.id, later.id]


def test_api_list_maintenance_slots_unauthenticated_ok(client):
    response = client.get("/api/maintenance-slots/")

    assert_status(response, 200)


def test_api_create_unauthenticated_returns_401(client):
    room = _create_room()

    response = client.post(
        "/api/maintenance-slots/",
        json={
            "room_id": room.id,
            "start_date": START.isoformat(),
            "end_date": END.isoformat(),
        },
    )

    assert_status(response, 401)


def test_api_create_non_admin_returns_403(client, login_as):
    login_as("REQUESTER")
    room = _create_room()

    response = client.post(
        "/api/maintenance-slots/",
        json={
            "room_id": room.id,
            "start_date": START.isoformat(),
            "end_date": END.isoformat(),
        },
    )

    assert_status(response, 403)


def test_api_create_admin_succeeds_and_sets_created_by_id(client, login_as):
    admin = login_as("ADMIN")
    room = _create_room()

    response = client.post(
        "/api/maintenance-slots/",
        json={
            "room_id": room.id,
            "start_date": START.isoformat(),
            "end_date": END.isoformat(),
        },
    )

    assert_status(response, 201)
    assert response.json["created_by_id"] == admin.id
    assert response.json["room_code"] == room.code
    assert response.json["created_by_name"] == admin.display_name


def test_api_create_unknown_room_returns_422(client, login_as):
    login_as("ADMIN")

    response = client.post(
        "/api/maintenance-slots/",
        json={
            "room_id": 999999,
            "start_date": START.isoformat(),
            "end_date": END.isoformat(),
        },
    )

    assert_status(response, 422)


def test_api_create_invalid_date_range_returns_422(client, login_as):
    login_as("ADMIN")
    room = _create_room()

    response = client.post(
        "/api/maintenance-slots/",
        json={
            "room_id": room.id,
            "start_date": END.isoformat(),
            "end_date": START.isoformat(),
        },
    )

    assert_status(response, 422)


def test_api_patch_unauthenticated_returns_401(client, login_as):
    admin = login_as("ADMIN")
    room = _create_room()
    slot = create_maintenance_slot(_slot_data(room.id, created_by_id=admin.id))
    client.get("/logout")

    response = client.patch(
        f"/api/maintenance-slots/{slot.id}/", json={"reason": "Rewiring"}
    )

    assert_status(response, 401)


def test_api_patch_non_admin_returns_403(client, login_as):
    admin = login_as("ADMIN")
    room = _create_room()
    slot = create_maintenance_slot(_slot_data(room.id, created_by_id=admin.id))

    login_as("REQUESTER")
    response = client.patch(
        f"/api/maintenance-slots/{slot.id}/", json={"reason": "Rewiring"}
    )

    assert_status(response, 403)


def test_api_patch_admin_succeeds(client, login_as):
    admin = login_as("ADMIN")
    room = _create_room()
    slot = create_maintenance_slot(_slot_data(room.id, created_by_id=admin.id))

    response = client.patch(
        f"/api/maintenance-slots/{slot.id}/", json={"reason": "Rewiring"}
    )

    assert_status(response, 200)
    assert response.json["reason"] == "Rewiring"


def test_api_patch_unknown_room_returns_422(client, login_as):
    admin = login_as("ADMIN")
    room = _create_room()
    slot = create_maintenance_slot(_slot_data(room.id, created_by_id=admin.id))

    response = client.patch(
        f"/api/maintenance-slots/{slot.id}/", json={"room_id": 999999}
    )

    assert_status(response, 422)


def test_api_patch_invalid_date_range_returns_422(client, login_as):
    admin = login_as("ADMIN")
    room = _create_room()
    slot = create_maintenance_slot(_slot_data(room.id, created_by_id=admin.id))

    response = client.patch(
        f"/api/maintenance-slots/{slot.id}/",
        json={"end_date": (START - timedelta(days=1)).isoformat()},
    )

    assert_status(response, 422)


def test_api_delete_unauthenticated_returns_401(client, login_as):
    admin = login_as("ADMIN")
    room = _create_room()
    slot = create_maintenance_slot(_slot_data(room.id, created_by_id=admin.id))
    client.get("/logout")

    response = client.delete(f"/api/maintenance-slots/{slot.id}/")

    assert_status(response, 401)


def test_api_delete_non_admin_returns_403(client, login_as):
    admin = login_as("ADMIN")
    room = _create_room()
    slot = create_maintenance_slot(_slot_data(room.id, created_by_id=admin.id))

    login_as("REQUESTER")
    response = client.delete(f"/api/maintenance-slots/{slot.id}/")

    assert_status(response, 403)


def test_api_delete_admin_succeeds(client, login_as):
    admin = login_as("ADMIN")
    room = _create_room()
    slot = create_maintenance_slot(_slot_data(room.id, created_by_id=admin.id))

    response = client.delete(f"/api/maintenance-slots/{slot.id}/")

    assert_status(response, 204)
    assert get_maintenance_slot(slot.id) is None


def test_html_list_fragment_without_hx_header_is_404(client, login_as):
    login_as("ADMIN")

    response = client.get("/maintenance-slots")

    assert_status(response, 404)


def test_html_list_fragment_unauthenticated_returns_401(client):
    mark_installed()

    response = client.get("/maintenance-slots", headers={"HX-Request": "true"})

    assert_status(response, 401)


def test_html_list_fragment_non_admin_returns_403(client, login_as):
    login_as("REQUESTER")

    response = client.get("/maintenance-slots", headers={"HX-Request": "true"})

    assert_status(response, 403)


def test_html_list_fragment_admin_renders_room_code(client, login_as):
    admin = login_as("ADMIN")
    room = _create_room()
    create_maintenance_slot(_slot_data(room.id, created_by_id=admin.id))

    response = client.get("/maintenance-slots", headers={"HX-Request": "true"})

    assert_status(response, 200)
    assert room.code in response.get_data(as_text=True)


def test_html_new_form_fragment_admin_renders(client, login_as):
    login_as("ADMIN")

    response = client.get("/maintenance-slots/new", headers={"HX-Request": "true"})

    assert_status(response, 200)
    assert "New Maintenance Slot" in response.get_data(as_text=True)


def test_html_create_unauthenticated_returns_401(client):
    mark_installed()
    room = _create_room()

    response = client.post("/maintenance-slots", data=_form_payload(room.id))

    assert_status(response, 401)


def test_html_create_non_admin_returns_403(client, login_as):
    login_as("REQUESTER")
    room = _create_room()

    response = client.post("/maintenance-slots", data=_form_payload(room.id))

    assert_status(response, 403)


def test_html_create_admin_renders_toast_and_room_code(client, login_as):
    login_as("ADMIN")
    room = _create_room()

    response = client.post("/maintenance-slots", data=_form_payload(room.id))

    assert_status(response, 200)
    body = response.get_data(as_text=True)
    assert room.code in body
    assert "created" in body


def test_html_create_invalid_date_range_returns_422_with_form_errors(client, login_as):
    login_as("ADMIN")
    room = _create_room()

    response = client.post(
        "/maintenance-slots",
        data=_form_payload(
            room.id, start_date=END.isoformat(), end_date=START.isoformat()
        ),
    )

    assert_status(response, 422)
    assert "end_date must be after start_date" in response.get_data(as_text=True)


def test_html_create_unknown_room_returns_422(client, login_as):
    login_as("ADMIN")

    response = client.post("/maintenance-slots", data=_form_payload(999999))

    assert_status(response, 422)


def test_html_edit_form_fragment_admin_renders(client, login_as):
    admin = login_as("ADMIN")
    room = _create_room()
    slot = create_maintenance_slot(_slot_data(room.id, created_by_id=admin.id))

    response = client.get(
        f"/maintenance-slots/{slot.id}/edit", headers={"HX-Request": "true"}
    )

    assert_status(response, 200)
    assert "Edit Maintenance Slot" in response.get_data(as_text=True)


def test_html_update_unauthenticated_returns_401(client, login_as):
    admin = login_as("ADMIN")
    room = _create_room()
    slot = create_maintenance_slot(_slot_data(room.id, created_by_id=admin.id))
    client.get("/logout")

    response = client.patch(
        f"/maintenance-slots/{slot.id}", data={"reason": "Rewiring"}
    )

    assert_status(response, 401)


def test_html_update_non_admin_returns_403(client, login_as):
    admin = login_as("ADMIN")
    room = _create_room()
    slot = create_maintenance_slot(_slot_data(room.id, created_by_id=admin.id))

    login_as("REQUESTER")
    response = client.patch(
        f"/maintenance-slots/{slot.id}", data={"reason": "Rewiring"}
    )

    assert_status(response, 403)


def test_html_update_admin_renders_toast_and_room_code(client, login_as):
    admin = login_as("ADMIN")
    room = _create_room()
    slot = create_maintenance_slot(_slot_data(room.id, created_by_id=admin.id))

    response = client.patch(
        f"/maintenance-slots/{slot.id}", data={"reason": "Rewiring"}
    )

    assert_status(response, 200)
    body = response.get_data(as_text=True)
    assert room.code in body
    assert "updated" in body


def test_html_update_invalid_room_returns_422(client, login_as):
    admin = login_as("ADMIN")
    room = _create_room()
    slot = create_maintenance_slot(_slot_data(room.id, created_by_id=admin.id))

    response = client.patch(f"/maintenance-slots/{slot.id}", data={"room_id": "999999"})

    assert_status(response, 422)


def test_html_delete_confirm_without_hx_header_is_404(client, login_as):
    admin = login_as("ADMIN")
    room = _create_room()
    slot = create_maintenance_slot(_slot_data(room.id, created_by_id=admin.id))

    response = client.get(f"/maintenance-slots/{slot.id}/delete/confirm")

    assert_status(response, 404)


def test_html_delete_confirm_renders_expected_copy(client, login_as):
    admin = login_as("ADMIN")
    room = _create_room()
    slot = create_maintenance_slot(_slot_data(room.id, created_by_id=admin.id))

    response = client.get(
        f"/maintenance-slots/{slot.id}/delete/confirm", headers={"HX-Request": "true"}
    )

    assert_status(response, 200)
    body = response.get_data(as_text=True)
    assert "Are you sure you want to delete the maintenance slot" in body
    assert room.code in body


def test_html_delete_unauthenticated_returns_401(client, login_as):
    admin = login_as("ADMIN")
    room = _create_room()
    slot = create_maintenance_slot(_slot_data(room.id, created_by_id=admin.id))
    client.get("/logout")

    response = client.delete(f"/maintenance-slots/{slot.id}")

    assert_status(response, 401)


def test_html_delete_non_admin_returns_403(client, login_as):
    admin = login_as("ADMIN")
    room = _create_room()
    slot = create_maintenance_slot(_slot_data(room.id, created_by_id=admin.id))

    login_as("REQUESTER")
    response = client.delete(f"/maintenance-slots/{slot.id}")

    assert_status(response, 403)


def test_html_delete_admin_renders_toast_and_removes_slot(client, login_as):
    admin = login_as("ADMIN")
    room = _create_room()
    slot = create_maintenance_slot(_slot_data(room.id, created_by_id=admin.id))

    response = client.delete(f"/maintenance-slots/{slot.id}")

    assert_status(response, 200)
    body = response.get_data(as_text=True)
    assert room.code in body
    assert "deleted" in body
    assert get_maintenance_slot(slot.id) is None


def test_successful_create_writes_single_audit_log_entry(client, login_as):
    admin = login_as("ADMIN")
    room = _create_room()

    response = client.post(
        "/api/maintenance-slots/",
        json={
            "room_id": room.id,
            "start_date": START.isoformat(),
            "end_date": END.isoformat(),
        },
    )
    assert_status(response, 201)
    slot_id = response.json["id"]

    logs = AuditLog.query.all()
    assert len(logs) == 1
    assert logs[0].action == "maintenance_slot.create"
    assert logs[0].entity_type == "maintenance_slot"
    assert logs[0].entity_id == slot_id
    assert logs[0].actor_id == admin.id
    assert logs[0].details == f"room={room.code}"


def test_successful_update_writes_single_audit_log_entry(client, login_as):
    admin = login_as("ADMIN")
    room = _create_room()
    slot = create_maintenance_slot(_slot_data(room.id, created_by_id=admin.id))

    response = client.patch(
        f"/api/maintenance-slots/{slot.id}/", json={"reason": "Rewiring"}
    )
    assert_status(response, 200)

    logs = AuditLog.query.all()
    assert len(logs) == 1
    assert logs[0].action == "maintenance_slot.update"
    assert logs[0].entity_type == "maintenance_slot"
    assert logs[0].entity_id == slot.id
    assert logs[0].actor_id == admin.id


def test_successful_delete_writes_single_audit_log_entry(client, login_as):
    admin = login_as("ADMIN")
    room = _create_room()
    slot = create_maintenance_slot(_slot_data(room.id, created_by_id=admin.id))
    slot_id = slot.id

    response = client.delete(f"/api/maintenance-slots/{slot_id}/")
    assert_status(response, 204)

    logs = AuditLog.query.all()
    assert len(logs) == 1
    assert logs[0].action == "maintenance_slot.delete"
    assert logs[0].entity_type == "maintenance_slot"
    assert logs[0].entity_id == slot_id
    assert logs[0].actor_id == admin.id


@pytest.mark.parametrize(
    "build_request",
    [
        lambda room: (
            "post",
            "/api/maintenance-slots/",
            {
                "room_id": room.id,
                "start_date": END.isoformat(),
                "end_date": START.isoformat(),
            },
        ),
        lambda room: (
            "post",
            "/api/maintenance-slots/",
            {
                "room_id": 999999,
                "start_date": START.isoformat(),
                "end_date": END.isoformat(),
            },
        ),
    ],
)
def test_rejected_invalid_create_writes_no_audit_log(client, login_as, build_request):
    login_as("ADMIN")
    room = _create_room()
    method, url, payload = build_request(room)

    response = getattr(client, method)(url, json=payload)

    assert_status(response, 422)
    assert AuditLog.query.count() == 0


def test_rejected_non_admin_create_writes_no_audit_log(client, login_as):
    login_as("REQUESTER")
    room = _create_room()

    response = client.post(
        "/api/maintenance-slots/",
        json={
            "room_id": room.id,
            "start_date": START.isoformat(),
            "end_date": END.isoformat(),
        },
    )

    assert_status(response, 403)
    assert AuditLog.query.count() == 0


def test_maintenance_slot_out_derived_fields_match_room_and_actor(client, login_as):
    admin = login_as("ADMIN")
    room = _create_room()
    slot = create_maintenance_slot(_slot_data(room.id, created_by_id=admin.id))

    response = client.get(f"/api/maintenance-slots/{slot.id}/")

    assert_status(response, 200)
    assert response.json["room_code"] == room.code
    assert response.json["created_by_name"] == admin.display_name
    assert response.json["created_by_id"] == admin.id
