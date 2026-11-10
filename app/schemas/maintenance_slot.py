from apiflask import Schema, fields, validators


class MaintenanceSlotIn(Schema):
    room_id = fields.Integer(required=True)
    start_date = fields.DateTime(required=True)
    end_date = fields.DateTime(required=True)
    reason = fields.String(
        required=False, allow_none=True, validate=validators.Length(max=256)
    )


class MaintenanceSlotOut(Schema):
    id = fields.Integer(dump_only=True)
    room_id = fields.Integer()
    room_code = fields.Method("get_room_code", dump_only=True)
    start_date = fields.DateTime()
    end_date = fields.DateTime()
    reason = fields.String(allow_none=True)
    created_by_id = fields.Integer(dump_only=True)
    created_by_name = fields.Method("get_created_by_name", dump_only=True)

    def get_room_code(self, obj):
        return obj.room.code if obj.room else None

    def get_created_by_name(self, obj):
        return obj.created_by.display_name if obj.created_by else None
