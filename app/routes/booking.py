from datetime import datetime

from flask import abort, render_template, request
from flask_login import current_user

from app.services.booking import create_booking
from app.services.calendar import build_slot_picker, build_week_view
from app.services.feature import list_features
from app.services.nav import can_access_module, grouped_visible_nav_items
from app.services.notify import render_toast
from app.services.page import htmx_only, render_page
from app.services.room import get_room, list_rooms


def register_booking_routes(app):
    @app.get("/booking")
    def booking_page():
        if not current_user.is_authenticated:
            abort(401)
        if not can_access_module(current_user.role, "booking"):
            abort(403)
        min_capacity = request.args.get("min_capacity", type=int)
        feature_ids = [int(v) for v in request.args.getlist("feature_ids")]
        rooms = list_rooms(min_capacity=min_capacity, feature_ids=feature_ids)
        return render_page(
            "partials/booking/room_list.html",
            nav_groups=grouped_visible_nav_items(current_user.role),
            title="Booking",
            rooms=rooms,
            all_features=list_features(),
            min_capacity=min_capacity,
            selected_feature_ids=feature_ids,
        )

    @app.get("/bookings/rooms/<int:room_id>")
    def booking_calendar(room_id):
        if not current_user.is_authenticated:
            abort(401)
        if not can_access_module(current_user.role, "booking"):
            abort(403)
        room = get_room(room_id)
        if room is None:
            abort(404)
        week_offset = request.args.get("week_offset", default=0, type=int)
        calendar = build_week_view(room_id, week_offset, current_user.id)
        return render_page(
            "partials/booking/calendar_view.html",
            nav_groups=grouped_visible_nav_items(current_user.role),
            title=f"Book {room.code}",
            room=room,
            week_offset=week_offset,
            **calendar,
        )

    @app.get("/bookings/rooms/<int:room_id>/slots/new")
    @htmx_only
    def booking_slot_new(room_id):
        if not current_user.is_authenticated:
            abort(401)
        if not can_access_module(current_user.role, "booking"):
            abort(403)
        room = get_room(room_id)
        if room is None:
            abort(404)
        row_start = datetime.fromisoformat(request.args["row_start"])
        row_end = datetime.fromisoformat(request.args["row_end"])
        gap_start = datetime.fromisoformat(request.args["gap_start"])
        gap_end = datetime.fromisoformat(request.args["gap_end"])
        week_offset = request.args.get("week_offset", default=0, type=int)
        picker = build_slot_picker(
            row_start,
            row_end,
            gap_start,
            gap_end,
            request.args.get("start"),
            request.args.get("slots", type=int),
        )
        return render_template(
            "partials/booking/slot_form.html",
            room=room,
            row_start_iso=row_start.isoformat(),
            row_end_iso=row_end.isoformat(),
            gap_start_iso=gap_start.isoformat(),
            gap_end_iso=gap_end.isoformat(),
            week_offset=week_offset,
            **picker,
        )

    @app.post("/bookings/rooms/<int:room_id>/slots")
    def booking_slot_create(room_id):
        if not current_user.is_authenticated:
            abort(401)
        if not can_access_module(current_user.role, "booking"):
            abort(403)
        room = get_room(room_id)
        if room is None:
            abort(404)

        row_start = datetime.fromisoformat(request.form["row_start"])
        row_end = datetime.fromisoformat(request.form["row_end"])
        gap_start = datetime.fromisoformat(request.form["gap_start"])
        gap_end = datetime.fromisoformat(request.form["gap_end"])
        week_offset = request.form.get("week_offset", default=0, type=int)
        picker = build_slot_picker(
            row_start,
            row_end,
            gap_start,
            gap_end,
            request.form.get("start"),
            request.form.get("slots", type=int),
        )

        def _render_form(error, status):
            return render_template(
                "partials/booking/slot_form.html",
                room=room,
                row_start_iso=row_start.isoformat(),
                row_end_iso=row_end.isoformat(),
                gap_start_iso=gap_start.isoformat(),
                gap_end_iso=gap_end.isoformat(),
                week_offset=week_offset,
                error=error,
                **picker,
            ), status

        if not picker["start_options"]:
            return _render_form("This slot is no longer available.", 422)

        try:
            create_booking(
                {
                    "start_date": picker["selected_start"],
                    "end_date": picker["end_time"],
                    "state": "PENDING",
                    "requester_id": current_user.id,
                    "room_id": room_id,
                }
            )
        except ValueError as err:
            return _render_form(str(err), 422)

        calendar = build_week_view(room_id, week_offset, current_user.id)
        return render_template(
            "partials/booking/booking_success.html",
            room=room,
            week_offset=week_offset,
            **calendar,
        ) + render_toast("success", f"Booking created for {room.code}.")
