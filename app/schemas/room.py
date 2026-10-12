from apiflask import Schema, fields, validators


class RoomIn(Schema):
    code = fields.String(required=True, validate=validators.Length(max=64))
    location = fields.String(required=True, validate=validators.Length(max=64))
    capacity = fields.Integer(required=True)
    feature_ids = fields.List(fields.Integer(), required=False, load_default=list)


class RoomOut(Schema):
    id = fields.Integer(dump_only=True)
    code = fields.String()
    location = fields.String()
    capacity = fields.Integer()
    feature_ids = fields.Method("get_feature_ids", dump_only=True)

    def get_feature_ids(self, obj):
        return [f.id for f in obj.features]
