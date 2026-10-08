from collections.abc import Callable
from dataclasses import dataclass, field

import pytest
from apiflask import fields, validators

from tests.helpers import (
    assert_fields_absent,
    assert_only_fields_changed,
    assert_status,
)

UNKNOWN_ID = 999999


@dataclass
class ApiContract:
    name: str
    url: str
    schema_in: type
    schema_out: type
    payload_factory: Callable[..., dict]
    unique_fields: tuple[str, ...] = field(default_factory=tuple)


def _detail_url(contract, resource_id):
    return f"{contract.url}{resource_id}/"


def _create(client, contract, payload=None):
    if payload is None:
        payload = contract.payload_factory()
    response = client.post(contract.url, json=payload)
    assert_status(response, 201)
    return response.json


def _schema_out_field_names(contract):
    return list(contract.schema_out().fields.keys())


def _load_only_field_names(contract):
    return [
        name
        for name, schema_field in contract.schema_in().fields.items()
        if schema_field.load_only
    ]


def _validators_of(schema_field):
    validate = getattr(schema_field, "validate", None)
    if validate is None:
        return []
    if isinstance(validate, (list, tuple)):
        return list(validate)
    return [validate]


def _alternate_value(contract, field_name, salt):
    schema_field = contract.schema_in().fields[field_name]
    base_value = contract.payload_factory()[field_name]
    field_validators = _validators_of(schema_field)

    one_of = next(
        (v for v in field_validators if isinstance(v, validators.OneOf)), None
    )
    if one_of is not None:
        for choice in one_of.choices:
            if choice != base_value:
                return choice
        raise ValueError(
            f"{contract.name}.{field_name}: no alternate OneOf choice available"
        )

    if isinstance(schema_field, fields.Email) and "@" in base_value:
        local, _, domain = base_value.partition("@")
        candidate = f"{local}+{salt}@{domain}"
    else:
        candidate = f"{base_value}-{salt}"

    max_length = next(
        (
            v.max
            for v in field_validators
            if isinstance(v, validators.Length) and v.max is not None
        ),
        None,
    )
    if max_length is not None and len(candidate) > max_length:
        candidate = candidate[:max_length]
    return candidate


def _two_payloads(contract, salt_a="a", salt_b="b"):
    overrides_a = {
        name: _alternate_value(contract, name, salt_a)
        for name in contract.unique_fields
    }
    overrides_b = {
        name: _alternate_value(contract, name, salt_b)
        for name in contract.unique_fields
    }
    return contract.payload_factory(**overrides_a), contract.payload_factory(
        **overrides_b
    )


def _collision_payloads(contract, collide_field):
    first, second = _two_payloads(contract)
    second = dict(second)
    second[collide_field] = first[collide_field]
    return first, second


def _patchable_field_name(contract):
    out_fields = set(_schema_out_field_names(contract))
    for name, schema_field in contract.schema_in().fields.items():
        if name in contract.unique_fields:
            continue
        if schema_field.load_only or schema_field.dump_only:
            continue
        if name in out_fields:
            return name
    raise ValueError(
        f"{contract.name}: no patchable field (every field is unique, load_only/dump_only, or absent from schema_out)"
    )


def _length_cases(validator):
    cases = []
    if validator.max is not None:
        cases.append(("too_long", "x" * (validator.max + 1)))
    if validator.min is not None and validator.min > 0:
        cases.append(("too_short", "x" * (validator.min - 1)))
    return cases


def _one_of_cases(validator):
    invalid_value = "__not_a_valid_choice__"
    assert invalid_value not in validator.choices
    return [("not_one_of", invalid_value)]


_VALIDATOR_CASE_BUILDERS = {
    validators.Length: _length_cases,
    validators.OneOf: _one_of_cases,
}


def _field_invalid_cases(schema_field):
    cases = []
    if isinstance(schema_field, fields.Email):
        cases.append(("invalid_email", "not-an-email"))
    for validator in _validators_of(schema_field):
        builder = _VALIDATOR_CASE_BUILDERS.get(type(validator))
        if builder is not None:
            cases.extend(builder(validator))
    return cases


def required_field_params(contracts):
    params = []
    for contract in contracts:
        for field_name, schema_field in contract.schema_in().fields.items():
            if schema_field.required:
                params.append(
                    pytest.param(
                        contract, field_name, id=f"{contract.name}-{field_name}"
                    )
                )
    return params


def invalid_value_params(contracts):
    params = []
    for contract in contracts:
        for field_name, schema_field in contract.schema_in().fields.items():
            for case_name, invalid_value in _field_invalid_cases(schema_field):
                params.append(
                    pytest.param(
                        contract,
                        field_name,
                        invalid_value,
                        id=f"{contract.name}-{field_name}-{case_name}",
                    )
                )
    return params


def unique_field_params(contracts):
    params = []
    for contract in contracts:
        for field_name in contract.unique_fields:
            params.append(
                pytest.param(contract, field_name, id=f"{contract.name}-{field_name}")
            )
    return params


def test_list_empty_returns_empty_list(client, contract):
    response = client.get(contract.url)

    assert_status(response, 200)
    assert response.json == []


def test_create_valid_returns_schema_out_fields_without_load_only_fields(
    client, contract
):
    payload = contract.payload_factory()

    body = _create(client, contract, payload)

    assert set(body.keys()) == set(_schema_out_field_names(contract))
    assert_fields_absent(body, *_load_only_field_names(contract))
    for field_name, value in payload.items():
        if field_name in body:
            assert body[field_name] == value


def test_list_after_create_returns_all_created(client, contract):
    first, second = _two_payloads(contract)
    created_ids = {
        _create(client, contract, first)["id"],
        _create(client, contract, second)["id"],
    }

    response = client.get(contract.url)

    assert_status(response, 200)
    assert {item["id"] for item in response.json} == created_ids


def test_get_by_id_returns_matching_resource(client, contract):
    created = _create(client, contract)

    response = client.get(_detail_url(contract, created["id"]))

    assert_status(response, 200)
    assert response.json == created


def test_get_unknown_id_returns_404(client, contract):
    response = client.get(_detail_url(contract, UNKNOWN_ID))

    assert_status(response, 404)


def test_patch_partial_update_changes_only_target_field(client, contract):
    field_name = _patchable_field_name(contract)
    created = _create(client, contract)
    new_value = _alternate_value(contract, field_name, "patched")

    response = client.patch(
        _detail_url(contract, created["id"]), json={field_name: new_value}
    )

    assert_status(response, 200)
    body = response.json
    assert body[field_name] == new_value
    assert_only_fields_changed(created, body, field_name)


def test_patch_unknown_id_returns_404(client, contract):
    field_name = _patchable_field_name(contract)
    new_value = _alternate_value(contract, field_name, "patched")

    response = client.patch(
        _detail_url(contract, UNKNOWN_ID), json={field_name: new_value}
    )

    assert_status(response, 404)


def test_delete_returns_204_then_404_on_get(client, contract):
    created = _create(client, contract)

    delete_response = client.delete(_detail_url(contract, created["id"]))
    assert_status(delete_response, 204)

    get_response = client.get(_detail_url(contract, created["id"]))
    assert_status(get_response, 404)


def test_delete_unknown_id_returns_404(client, contract):
    response = client.delete(_detail_url(contract, UNKNOWN_ID))

    assert_status(response, 404)


def check_required_field_missing_returns_422(client, contract, field_name):
    payload = contract.payload_factory()
    del payload[field_name]

    response = client.post(contract.url, json=payload)

    assert_status(response, 422)


def check_invalid_value_returns_422(client, contract, field_name, invalid_value):
    payload = contract.payload_factory(**{field_name: invalid_value})

    response = client.post(contract.url, json=payload)

    assert_status(response, 422)


def check_create_duplicate_unique_field_returns_409(client, contract, field_name):
    first, second = _collision_payloads(contract, field_name)

    _create(client, contract, first)
    response = client.post(contract.url, json=second)

    assert_status(response, 409)


def check_patch_duplicate_unique_field_returns_409(client, contract, field_name):
    first, second = _two_payloads(contract)
    created_first = _create(client, contract, first)
    created_second = _create(client, contract, second)

    response = client.patch(
        _detail_url(contract, created_second["id"]),
        json={field_name: created_first[field_name]},
    )

    assert_status(response, 409)
