from apiflask import APIBlueprint, EmptySchema, abort

from app.schemas.booking import BookingIn, BookingOut
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
def create_booking_view(json_data):
    try:
        booking = create_booking(json_data)
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
def update_booking_view(booking_id, json_data):
    booking = get_booking(booking_id)
    if booking is None:
        abort(404, message="Booking not found.")
    try:
        booking = update_booking(booking, json_data)
        return booking
    except ValueError as err:
        abort(422, message=str(err))


@bookings_blp.delete("/<int:booking_id>/")
@bookings_blp.output(EmptySchema, status_code=204)
def delete_booking_view(booking_id):
    booking = get_booking(booking_id)
    if booking is None:
        abort(404, message="Booking not found.")
    delete_booking(booking)
