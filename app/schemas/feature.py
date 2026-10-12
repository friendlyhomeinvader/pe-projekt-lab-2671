from apiflask import Schema, fields, validators


class FeatureIn(Schema):
    name = fields.String(required=True, validate=validators.Length(max=64))
    description = fields.String(validate=validators.Length(max=256))


class FeatureOut(Schema):
    id = fields.Integer(dump_only=True)
    name = fields.String()
    description = fields.String()
