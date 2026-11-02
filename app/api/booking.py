from apiflask import APIBlueprint, EmptySchema, abort
from flask_login import current_user

from app.schemas.booking import BookingIn, BookingOut
from app.services.audit import log_action
from app.services.auth import role_required
from app.services.booking import (
    create_booking,
    delete_booking,
    get_booking,
    list_bookings,
    update_booking,
)

bookings_blp = APIBlueprint(
    "bookings", __name__, url_prefix="/api/bookings", tag="Bookings"
)


@bookings_blp.get("/")
@bookings_blp.output(BookingOut(many=True))
def get_bookings():
    return list_bookings()


@bookings_blp.post("/")
@bookings_blp.input(BookingIn)
@bookings_blp.output(BookingOut, status_code=201)
@role_required("REQUESTER")
def create_booking_view(json_data):
    try:
        booking = create_booking(json_data)
        log_action(
            current_user.id if current_user.is_authenticated else None,
            "booking.create",
            entity_type="booking",
            entity_id=booking.id,
        )
        return booking
    except ValueError as err:
        abort(422, message=str(err))


@bookings_blp.get("/<int:booking_id>/")
@bookings_blp.output(BookingOut)
def get_booking_view(booking_id):
    booking = get_booking(booking_id)
    if booking is None:
        abort(404, message="Booking not found.")
    return booking


@bookings_blp.patch("/<int:booking_id>/")
@bookings_blp.input(BookingIn(partial=True))
@bookings_blp.output(BookingOut)
@role_required("REQUESTER")
def update_booking_view(booking_id, json_data):
    booking = get_booking(booking_id)
    if booking is None:
        abort(404, message="Booking not found.")
    try:
        booking = update_booking(booking, json_data)
        log_action(
            current_user.id if current_user.is_authenticated else None,
            "booking.update",
            entity_type="booking",
            entity_id=booking.id,
        )
        return booking
    except ValueError as err:
        abort(422, message=str(err))


@bookings_blp.delete("/<int:booking_id>/")
@bookings_blp.output(EmptySchema, status_code=204)
@role_required("REQUESTER")
def delete_booking_view(booking_id):
    booking = get_booking(booking_id)
    if booking is None:
        abort(404, message="Booking not found.")
    booking_id_value = booking.id
    delete_booking(booking)
    log_action(
        current_user.id if current_user.is_authenticated else None,
        "booking.delete",
        entity_type="booking",
        entity_id=booking_id_value,
    )
