import itertools
from datetime import datetime, timedelta, timezone

import pytest

from app import db
from app.models.booking import Booking
from app.models.room import Feature, Room
from app.models.user import User
from app.services.booking import (
    create_booking,
    missing_room_features,
    update_booking,
)
from app.services.calendar import build_week_view
from tests.factories import booking_payload
from tests.helpers import assert_status

_counter = itertools.count()

BASE_START = datetime(2027, 3, 1, 9, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None)
BASE_END = BASE_START + timedelta(minutes=45)


def _create_room(**overrides):
    n = next(_counter)
    defaults = {"code": f"BF{n}", "location": "Building BF", "capacity": 10}
    defaults.update(overrides)
    room = Room(**defaults)
    db.session.add(room)
    db.session.commit()
    return room


def _create_requester(**overrides):
    n = next(_counter)
    defaults = {
        "username": f"bf.requester.{n}",
        "display_name": f"BF Requester {n}",
        "email": f"bf.requester.{n}@uni.su",
        "role": "REQUESTER",
    }
    defaults.update(overrides)
    user = User(**defaults)
    user.set_password("Password123456!!")
    db.session.add(user)
    db.session.commit()
    return user


def _create_feature(**overrides):
    n = next(_counter)
    defaults = {"name": f"Feature {n}", "description": "test feature"}
    defaults.update(overrides)
    feature = Feature(**defaults)
    db.session.add(feature)
    db.session.commit()
    return feature


def _booking_data(room_id, requester_id, **overrides):
    payload = {
        "start_date": BASE_START,
        "end_date": BASE_END,
        "state": "PENDING",
        "requester_id": requester_id,
        "room_id": room_id,
    }
    payload.update(overrides)
    return payload


def _slot_form_payload(feature_ids=None, **overrides):
    row_start_iso = BASE_START.isoformat()
    row_end_iso = (BASE_START + timedelta(hours=1)).isoformat()
    payload = {
        "row_start": row_start_iso,
        "row_end": row_end_iso,
        "gap_start": row_start_iso,
        "gap_end": row_end_iso,
        "week_offset": "0",
        "start": row_start_iso,
        "slots": "1",
    }
    if feature_ids:
        payload["feature_ids"] = [str(f) for f in feature_ids]
    payload.update(overrides)
    return payload


def _week_offset_for(target_date, today):
    target_monday = target_date - timedelta(days=target_date.weekday())
    this_monday = today - timedelta(days=today.weekday())
    return (target_monday - this_monday).days // 7


def test_create_booking_with_feature_ids_attaches_features(client):
    room = _create_room()
    requester = _create_requester()
    f1 = _create_feature()
    f2 = _create_feature()

    booking = create_booking(
        _booking_data(room.id, requester.id, feature_ids=[f1.id, f2.id])
    )

    assert {f.id for f in booking.features} == {f1.id, f2.id}


def test_create_booking_with_unknown_feature_id_raises(client):
    room = _create_room()
    requester = _create_requester()

    with pytest.raises(ValueError) as exc_info:
        create_booking(_booking_data(room.id, requester.id, feature_ids=[999999]))

    assert "999999" in str(exc_info.value)
    assert Booking.query.count() == 0


def test_create_booking_without_feature_ids_defaults_to_empty(client):
    room = _create_room()
    requester = _create_requester()

    booking = create_booking(_booking_data(room.id, requester.id))

    assert booking.features == []


def test_update_booking_feature_ids_replaces_existing_set(client):
    room = _create_room()
    requester = _create_requester()
    f1 = _create_feature()
    f2 = _create_feature()
    booking = create_booking(_booking_data(room.id, requester.id, feature_ids=[f1.id]))

    updated = update_booking(booking, {"feature_ids": [f2.id]})

    assert {f.id for f in updated.features} == {f2.id}


def test_update_booking_with_unknown_feature_id_raises(client):
    room = _create_room()
    requester = _create_requester()
    f1 = _create_feature()
    booking = create_booking(_booking_data(room.id, requester.id, feature_ids=[f1.id]))

    with pytest.raises(ValueError) as exc_info:
        update_booking(booking, {"feature_ids": [999999]})

    assert "999999" in str(exc_info.value)
    assert {f.id for f in booking.features} == {f1.id}


def test_update_booking_without_feature_ids_key_leaves_associations_untouched(client):
    room = _create_room()
    requester = _create_requester()
    f1 = _create_feature()
    booking = create_booking(_booking_data(room.id, requester.id, feature_ids=[f1.id]))

    updated = update_booking(booking, {"state": "ACTIVE"})

    assert updated.state == "ACTIVE"
    assert {f.id for f in updated.features} == {f1.id}


def test_missing_room_features_returns_features_room_lacks(client):
    room = _create_room()
    requester = _create_requester()
    room_feature = _create_feature(name="On room")
    missing_feature = _create_feature(name="Not on room")
    room.features = [room_feature]
    db.session.commit()

    booking = create_booking(
        _booking_data(
            room.id, requester.id, feature_ids=[room_feature.id, missing_feature.id]
        )
    )

    missing = missing_room_features(booking)

    assert {f.id for f in missing} == {missing_feature.id}


def test_missing_room_features_empty_when_subset_of_room_features(client):
    room = _create_room()
    requester = _create_requester()
    room_feature = _create_feature(name="On room")
    room.features = [room_feature]
    db.session.commit()

    booking = create_booking(
        _booking_data(room.id, requester.id, feature_ids=[room_feature.id])
    )

    assert missing_room_features(booking) == []


def test_missing_room_features_empty_when_booking_has_no_features(client):
    room = _create_room()
    requester = _create_requester()

    booking = create_booking(_booking_data(room.id, requester.id))

    assert missing_room_features(booking) == []


def test_api_create_booking_with_feature_ids_returns_them(client, login_as):
    login_as("ADMIN")
    f1 = _create_feature()
    f2 = _create_feature()

    response = client.post(
        "/api/bookings/",
        json=booking_payload(feature_ids=[f1.id, f2.id]),
    )

    assert_status(response, 201)
    assert set(response.json["feature_ids"]) == {f1.id, f2.id}


def test_api_patch_booking_changes_feature_ids(client, login_as):
    login_as("ADMIN")
    f1 = _create_feature()
    f2 = _create_feature()
    created = client.post(
        "/api/bookings/", json=booking_payload(feature_ids=[f1.id])
    ).json

    response = client.patch(
        f"/api/bookings/{created['id']}/", json={"feature_ids": [f2.id]}
    )

    assert_status(response, 200)
    assert response.json["feature_ids"] == [f2.id]


def test_api_create_booking_with_unknown_feature_id_returns_422(client, login_as):
    login_as("ADMIN")

    response = client.post("/api/bookings/", json=booking_payload(feature_ids=[999999]))

    assert_status(response, 422)
    assert "999999" in response.json["message"]


def test_html_booking_slot_create_with_feature_ids_attaches_features(client, login_as):
    login_as("REQUESTER")
    room = _create_room()
    f1 = _create_feature()
    f2 = _create_feature()

    response = client.post(
        f"/bookings/rooms/{room.id}/slots",
        data=_slot_form_payload(feature_ids=[f1.id, f2.id]),
    )

    assert_status(response, 200)
    booking = Booking.query.filter_by(room_id=room.id).one()
    assert {f.id for f in booking.features} == {f1.id, f2.id}


def test_html_booking_slot_create_without_feature_ids_attaches_none(client, login_as):
    login_as("REQUESTER")
    room = _create_room()

    response = client.post(
        f"/bookings/rooms/{room.id}/slots",
        data=_slot_form_payload(),
    )

    assert_status(response, 200)
    booking = Booking.query.filter_by(room_id=room.id).one()
    assert booking.features == []


def test_build_week_view_label_includes_needs_when_feature_missing_from_room(client):
    room = _create_room()
    requester = _create_requester()
    missing_feature = _create_feature(name="Projector")

    create_booking(
        _booking_data(room.id, requester.id, feature_ids=[missing_feature.id])
    )
    week_offset = _week_offset_for(BASE_START.date(), datetime.now(timezone.utc).date())

    view = build_week_view(room.id, week_offset, requester.id)

    day = next(d for d in view["days"] if d["date"] == BASE_START.date())
    assert "needs: Projector" in day["bookings"][0]["label"]


def test_build_week_view_label_omits_needs_when_features_subset_of_room(client):
    room = _create_room()
    requester = _create_requester()
    room_feature = _create_feature(name="Whiteboard")
    room.features = [room_feature]
    db.session.commit()

    create_booking(_booking_data(room.id, requester.id, feature_ids=[room_feature.id]))
    week_offset = _week_offset_for(BASE_START.date(), datetime.now(timezone.utc).date())

    view = build_week_view(room.id, week_offset, requester.id)

    day = next(d for d in view["days"] if d["date"] == BASE_START.date())
    assert "needs:" not in day["bookings"][0]["label"]
