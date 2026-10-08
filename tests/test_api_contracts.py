import pytest

from tests.contract import (
    check_create_duplicate_unique_field_returns_409,
    check_invalid_value_returns_422,
    check_patch_duplicate_unique_field_returns_409,
    check_required_field_missing_returns_422,
    invalid_value_params,
    required_field_params,
    test_create_valid_returns_schema_out_fields_without_load_only_fields,
    test_delete_returns_204_then_404_on_get,
    test_delete_unknown_id_returns_404,
    test_get_by_id_returns_matching_resource,
    test_get_unknown_id_returns_404,
    test_list_after_create_returns_all_created,
    test_list_empty_returns_empty_list,
    test_patch_partial_update_changes_only_target_field,
    test_patch_unknown_id_returns_404,
    unique_field_params,
)
from tests.registered_contracts import ALL_CONTRACTS

contracts = pytest.mark.parametrize(
    "contract", ALL_CONTRACTS, ids=[contract.name for contract in ALL_CONTRACTS]
)

test_list_empty_returns_empty_list = contracts(test_list_empty_returns_empty_list)
test_create_valid_returns_schema_out_fields_without_load_only_fields = contracts(
    test_create_valid_returns_schema_out_fields_without_load_only_fields
)
test_list_after_create_returns_all_created = contracts(
    test_list_after_create_returns_all_created
)
test_get_by_id_returns_matching_resource = contracts(
    test_get_by_id_returns_matching_resource
)
test_get_unknown_id_returns_404 = contracts(test_get_unknown_id_returns_404)
test_patch_partial_update_changes_only_target_field = contracts(
    test_patch_partial_update_changes_only_target_field
)
test_patch_unknown_id_returns_404 = contracts(test_patch_unknown_id_returns_404)
test_delete_returns_204_then_404_on_get = contracts(
    test_delete_returns_204_then_404_on_get
)
test_delete_unknown_id_returns_404 = contracts(test_delete_unknown_id_returns_404)


@pytest.mark.parametrize("contract, field_name", required_field_params(ALL_CONTRACTS))
def test_create_missing_required_field_returns_422(client, contract, field_name):
    check_required_field_missing_returns_422(client, contract, field_name)


@pytest.mark.parametrize(
    "contract, field_name, invalid_value", invalid_value_params(ALL_CONTRACTS)
)
def test_create_invalid_value_returns_422(client, contract, field_name, invalid_value):
    check_invalid_value_returns_422(client, contract, field_name, invalid_value)


@pytest.mark.parametrize("contract, field_name", unique_field_params(ALL_CONTRACTS))
def test_create_duplicate_unique_field_returns_409(client, contract, field_name):
    check_create_duplicate_unique_field_returns_409(client, contract, field_name)


@pytest.mark.parametrize("contract, field_name", unique_field_params(ALL_CONTRACTS))
def test_patch_duplicate_unique_field_returns_409(client, contract, field_name):
    check_patch_duplicate_unique_field_returns_409(client, contract, field_name)
