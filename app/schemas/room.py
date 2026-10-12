from apiflask import Schema, fields, validators


class RoomIn(Schema):
    code = fields.String(required=True, validate=validators.Length(max=64))
    location = fields.String(required=True, validate=validators.Length(max=64))
    capacity = fields.Integer(required=True)


class RoomOut(Schema):
    id = fields.Integer(dump_only=True)
    code = fields.String()
    location = fields.String()
    capacity = fields.Integer()
