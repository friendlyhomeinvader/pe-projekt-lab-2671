import pytest

from tests.contract import test_list_empty_returns_empty_list

from tests.registered_contracts import ALL_CONTRACTS

contracts = pytest.mark.parametrize(
    "contract", ALL_CONTRACTS, ids=[contract.name for contract in ALL_CONTRACTS]
)

test_list_empty_returns_empty_list = contracts(
    test_list_empty_returns_empty_list)
