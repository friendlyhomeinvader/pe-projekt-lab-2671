from apiflask import Schema, fields


class KeyAuthorizationGrantIn(Schema):
    key_id = fields.Integer(required=True)
    assignee_id = fields.Integer(required=True)
    assigner_id = fields.Integer(required=True)


class KeyAuthorizationOut(Schema):
    id = fields.Integer(dump_only=True)
    key_id = fields.Integer()
    assignee_id = fields.Integer()
    assigner_id = fields.Integer()
    granted_at = fields.DateTime(dump_only=True)
    revoked_at = fields.DateTime(allow_none=True, dump_only=True)
