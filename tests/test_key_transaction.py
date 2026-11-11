import itertools

import pytest

from app import db
from app.models.key import Key
from app.models.room import Room
from app.models.user import User
from app.services.key_transaction import issue_key, return_key

_counter = itertools.count()


def _create_room(**overrides):
    n = next(_counter)
    defaults = {"code": f"KT{n}", "location": "Building KT", "capacity": 10}
    defaults.update(overrides)
    room = Room(**defaults)
    db.session.add(room)
    db.session.commit()
    return room


def _create_key(room, **overrides):
    n = next(_counter)
    defaults = {"tag": f"KT-KEY-{n}", "is_master_key": False, "room_id": room.id}
    defaults.update(overrides)
    key = Key(**defaults)
    db.session.add(key)
    db.session.commit()
    return key


def _create_user(role, **overrides):
    n = next(_counter)
    defaults = {
        "username": f"kt.{role.lower()}.{n}",
        "display_name": f"KT {role.title()} {n}",
        "email": f"kt.{role.lower()}.{n}@uni.su",
        "role": role,
    }
    defaults.update(overrides)
    user = User(**defaults)
    user.set_password("Password123456!!")
    db.session.add(user)
    db.session.commit()
    return user


def _issue(
    key, operator, holder, identification_type="PIN", identification_value="1234"
):
    return issue_key(
        key,
        identification_type=identification_type,
        identification_value=identification_value,
        operator_id=operator.id,
        holder_id=holder.id,
    )


def test_return_requires_identification(client):
    room = _create_room()
    key = _create_key(room)
    operator = _create_user("OPERATOR")
    holder = _create_user("REQUESTER")
    transaction = _issue(key, operator, holder)

    with pytest.raises(ValueError):
        return_key(transaction, identification_type="PIN", identification_value="")

    assert transaction.state == "ISSUED"


def test_return_rejects_unknown_identification_type(client):
    room = _create_room()
    key = _create_key(room)
    operator = _create_user("OPERATOR")
    holder = _create_user("REQUESTER")
    transaction = _issue(key, operator, holder)

    with pytest.raises(ValueError):
        return_key(
            transaction, identification_type="FINGERPRINT", identification_value="1234"
        )

    assert transaction.state == "ISSUED"


def test_return_rejects_mismatched_identification_value(client):
    room = _create_room()
    key = _create_key(room)
    operator = _create_user("OPERATOR")
    holder = _create_user("REQUESTER")
    transaction = _issue(key, operator, holder, identification_value="1234")

    with pytest.raises(ValueError, match="does not match"):
        return_key(transaction, identification_type="PIN", identification_value="9999")

    assert transaction.state == "ISSUED"


def test_return_rejects_mismatched_identification_type(client):
    room = _create_room()
    key = _create_key(room)
    operator = _create_user("OPERATOR")
    holder = _create_user("REQUESTER")
    transaction = _issue(key, operator, holder, identification_type="PIN")

    with pytest.raises(ValueError, match="does not match"):
        return_key(transaction, identification_type="CARD", identification_value="1234")

    assert transaction.state == "ISSUED"


def test_return_succeeds_with_matching_identification(client):
    room = _create_room()
    key = _create_key(room)
    operator = _create_user("OPERATOR")
    holder = _create_user("REQUESTER")
    transaction = _issue(
        key, operator, holder, identification_type="CARD", identification_value="A1B2"
    )

    returned = return_key(
        transaction, identification_type="CARD", identification_value="A1B2"
    )

    assert returned.state == "RETURNED"
    assert returned.returned_at is not None


def test_html_return_without_identification_returns_422(client, login_as):
    login_as("OPERATOR")
    room = _create_room()
    key = _create_key(room)
    operator = _create_user("OPERATOR")
    holder = _create_user("REQUESTER")
    _issue(key, operator, holder)

    response = client.post(
        f"/key-handling/keys/{key.id}/return",
        data={"room_condition_notes": "Fine."},
    )

    assert response.status_code == 422
    assert "Identification" in response.get_data(as_text=True)


def test_html_return_with_wrong_identification_returns_422(client, login_as):
    login_as("OPERATOR")
    room = _create_room()
    key = _create_key(room)
    operator = _create_user("OPERATOR")
    holder = _create_user("REQUESTER")
    _issue(key, operator, holder, identification_value="1234")

    response = client.post(
        f"/key-handling/keys/{key.id}/return",
        data={
            "identification_type": "PIN",
            "identification_value": "0000",
            "room_condition_notes": "Fine.",
        },
    )

    assert response.status_code == 422
    assert "does not match" in response.get_data(as_text=True)


def test_html_return_with_matching_identification_succeeds(client, login_as):
    login_as("OPERATOR")
    room = _create_room()
    key = _create_key(room)
    operator = _create_user("OPERATOR")
    holder = _create_user("REQUESTER")
    _issue(key, operator, holder, identification_value="1234")

    response = client.post(
        f"/key-handling/keys/{key.id}/return",
        data={
            "identification_type": "PIN",
            "identification_value": "1234",
            "room_condition_notes": "Fine.",
        },
    )

    assert response.status_code == 200
    assert "returned" in response.get_data(as_text=True)
