from app.schemas.feature import FeatureIn, FeatureOut
from app.schemas.room import RoomIn, RoomOut
from app.schemas.user import UserIn, UserOut
from tests.contract import ApiContract
from tests.factories import feature_payload, room_payload, user_payload

USER_CONTRACT = ApiContract(
    name="users",
    url="/api/users/",
    schema_in=UserIn,
    schema_out=UserOut,
    payload_factory=user_payload,
    unique_fields=("username", "email"),
)

ROOM_CONTRACT = ApiContract(
    name="rooms",
    url="/api/rooms/",
    schema_in=RoomIn,
    schema_out=RoomOut,
    payload_factory=room_payload,
    unique_fields=(),
)

FEATURE_CONTRACT = ApiContract(
    name="features",
    url="/api/features/",
    schema_in=FeatureIn,
    schema_out=FeatureOut,
    payload_factory=feature_payload,
    unique_fields=(),
)

ALL_CONTRACTS = [USER_CONTRACT, ROOM_CONTRACT, FEATURE_CONTRACT]
