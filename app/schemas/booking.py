from apiflask import Schema, fields, validators

from app.models.booking import BOOKING_STATES


class BookingIn(Schema):
    start_date = fields.DateTime(required=True)
    end_date = fields.DateTime(required=True)
    state = fields.String(required=True, validate=validators.OneOf(BOOKING_STATES))
    requester_id = fields.Integer(required=True)
    room_id = fields.Integer(required=True)
    feature_ids = fields.List(fields.Integer(), required=False, load_default=list)


class BookingOut(Schema):
    id = fields.Integer(dump_only=True)
    start_date = fields.DateTime()
    end_date = fields.DateTime()
    state = fields.String()
    requester_id = fields.Integer()
    room_id = fields.Integer()
    feature_ids = fields.Method("get_feature_ids", dump_only=True)

    def get_feature_ids(self, obj):
        return [f.id for f in obj.features]
