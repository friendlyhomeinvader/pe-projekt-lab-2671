from apiflask import Schema, fields, validators

from app.models.user import USER_ROLES


class UserIn(Schema):
    username = fields.String(required=True, validate=validators.Length(max=64))
    display_name = fields.String(required=True, validate=validators.Length(max=256))
    email = fields.Email(required=True, validate=validators.Length(max=256))
    role = fields.String(required=True, validate=validators.OneOf(USER_ROLES))
    password = fields.String(required=True, load_only=True, validate=validators.Length(min=8))


class UserOut(Schema):
    id = fields.Integer(dump_only=True)
    username = fields.String()
    display_name = fields.String()
    email = fields.Email()
    role = fields.String()
