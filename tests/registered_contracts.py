from app.schemas.user import UserIn, UserOut
from tests.contract import ApiContract
from tests.factories import user_payload

USER_CONTRACT = ApiContract(
    name="users",
    url="/api/users/",
    schema_in=UserIn,
    schema_out=UserOut,
    payload_factory=user_payload,
    unique_fields=("username", "email"),
)

ALL_CONTRACTS = [USER_CONTRACT]
