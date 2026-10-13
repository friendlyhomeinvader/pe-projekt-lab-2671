from apiflask import Schema, fields, validators

from app.models.booking import BOOKING_STATES


class BookingIn(Schema):
    start_date = fields.DateTime(required=True)
    end_date = fields.DateTime(required=True)
    state = fields.String(required=True, validate=validators.OneOf(BOOKING_STATES))
    requester_id = fields.Integer(required=True)
    room_id = fields.Integer(required=True)


class BookingOut(Schema):
    id = fields.Integer(dump_only=True)
    start_date = fields.DateTime()
    end_date = fields.DateTime()
    state = fields.String()
    requester_id = fields.Integer()
    room_id = fields.Integer()
