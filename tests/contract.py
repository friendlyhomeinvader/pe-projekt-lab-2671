from collections.abc import Callable
from dataclasses import dataclass, field

@dataclass
class ApiContract:
    name: str
    url: str
    schema_in: type
    schema_out: type
    payload_factory: Callable[..., dict]
    unique_fields: tuple[str, ...] = field(default_factory=tuple)


def test_list_empty_returns_empty_list(client, contract):
    response = client.get(contract.url)
    assert response.status_code == 200
    assert response.json == []
