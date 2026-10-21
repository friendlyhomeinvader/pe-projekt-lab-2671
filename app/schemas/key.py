from apiflask import Schema, fields, validators


class KeyIn(Schema):
    tag = fields.String(required=True, validate=validators.Length(max=64))
    is_master_key = fields.Boolean(load_default=False)
    room_id = fields.Integer(required=False, allow_none=True, load_default=None)
    room_ids = fields.List(fields.Integer(), required=False, load_default=list)


class KeyOut(Schema):
    id = fields.Integer(dump_only=True)
    tag = fields.String()
    is_master_key = fields.Boolean()
    room_id = fields.Integer(allow_none=True)
    room_ids = fields.Method("get_room_ids", dump_only=True)

    def get_room_ids(self, obj):
        return [r.id for r in obj.rooms]
