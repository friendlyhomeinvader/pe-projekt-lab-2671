from flask import abort, render_template, request
from flask_login import current_user

from app import db
from app.models.booking import Booking
from app.services.auth import role_required
from app.services.booking import (
    get_booking,
    list_in_progress_and_upcoming_bookings,
    list_unresolved_bookings,
)
from app.services.key import get_key, list_authorized_keys
from app.services.key_transaction import (
    eligible_bookings_for_key,
    eligible_holders,
    find_upcoming_booking_within,
    get_open_transaction,
    is_key_out,
    issue_key,
    key_room_ids,
    open_transactions_by_key_id,
    resolve_key_for_booking,
    return_key,
)
from app.services.notify import render_toast
from app.services.page import htmx_only


def _issue_form_context_for_key(key, booking_id_raw):
    selected_booking = None
    if booking_id_raw:
        candidate = db.session.get(Booking, int(booking_id_raw))
        eligible = eligible_bookings_for_key(key)
        if candidate is not None and candidate.id in {b.id for b in eligible}:
            selected_booking = candidate
    return {
        "key": key,
        "entry": "key",
        "bookings": eligible_bookings_for_key(key),
        "selected_booking_id": selected_booking.id if selected_booking else None,
        "booking": None,
        "linked_booking": selected_booking,
        "selected_holder_id": selected_booking.requester_id if selected_booking else None,
        "warning_booking": (
            find_upcoming_booking_within(key_room_ids(key)) if selected_booking is None else None
        ),
        "all_users": eligible_holders(),
        "error": None,
    }


def register_key_transaction_routes(app):
    @app.get("/key-handling/keys/<int:key_id>/transaction")
    @htmx_only
    @role_required("OPERATOR")
    def key_handling_key_transaction(key_id):
        key = get_key(key_id)
        if key is None:
            abort(404)
        if is_key_out(key.id):
            return render_template(
                "partials/key_handling/return_form.html",
                key=key,
                transaction=get_open_transaction(key.id),
                entry="key",
                booking=None,
                error=None,
            )
        context = _issue_form_context_for_key(key, None)
        return render_template("partials/key_handling/issue_form.html", **context)

    @app.get("/key-handling/keys/<int:key_id>/issue-form")
    @htmx_only
    @role_required("OPERATOR")
    def key_handling_key_issue_form(key_id):
        key = get_key(key_id)
        if key is None:
            abort(404)
        booking_id_raw = request.args.get("booking_id") or None
        context = _issue_form_context_for_key(key, booking_id_raw)
        return render_template("partials/key_handling/issue_form.html", **context)

    @app.post("/key-handling/keys/<int:key_id>/issue")
    @role_required("OPERATOR")
    def key_handling_key_issue(key_id):
        key = get_key(key_id)
        if key is None:
            abort(404)

        holder_id = request.form.get("holder_id")
        identification_type = request.form.get("identification_type")
        identification_value = request.form.get("identification_value", "").strip()
        booking_id_raw = request.form.get("booking_id") or None

        try:
            transaction = issue_key(
                key,
                holder_id=int(holder_id) if holder_id else None,
                identification_type=identification_type,
                identification_value=identification_value,
                operator_id=current_user.id,
                booking_id=int(booking_id_raw) if booking_id_raw else None,
            )
        except (ValueError, TypeError) as err:
            context = _issue_form_context_for_key(key, booking_id_raw)
            context["selected_holder_id"] = int(holder_id) if holder_id else context["selected_holder_id"]
            context["error"] = str(err)
            return render_template("partials/key_handling/issue_form.html", **context), 422

        keys = list_authorized_keys()
        return render_template(
            "partials/key_handling/_keys_list_oob.html",
            keys=keys,
            open_by_key=open_transactions_by_key_id([k.id for k in keys]),
        ) + render_toast("success", f"{key.tag} issued to {transaction.holder.display_name}.")

    @app.post("/key-handling/keys/<int:key_id>/return")
    @role_required("OPERATOR")
    def key_handling_key_return(key_id):
        key = get_key(key_id)
        if key is None:
            abort(404)
        transaction = get_open_transaction(key.id)
        if transaction is None:
            abort(404)

        try:
            return_key(
                transaction,
                room_condition_notes=request.form.get("room_condition_notes"),
                damage_reported="damage_reported" in request.form,
            )
        except ValueError as err:
            return render_template(
                "partials/key_handling/return_form.html",
                key=key,
                transaction=transaction,
                entry="key",
                booking=None,
                error=str(err),
            ), 422

        keys = list_authorized_keys()
        return render_template(
            "partials/key_handling/_keys_list_oob.html",
            keys=keys,
            open_by_key=open_transactions_by_key_id([k.id for k in keys]),
        ) + render_toast("success", f"{key.tag} returned.")

    @app.get("/key-handling/bookings/<int:booking_id>/transaction")
    @htmx_only
    @role_required("OPERATOR")
    def key_handling_booking_transaction(booking_id):
        booking = get_booking(booking_id)
        if booking is None:
            abort(404)
        key = resolve_key_for_booking(booking)
        if key is None:
            return render_template(
                "partials/key_handling/no_key_available.html", booking=booking
            )
        if is_key_out(key.id):
            return render_template(
                "partials/key_handling/return_form.html",
                key=key,
                transaction=get_open_transaction(key.id),
                entry="booking",
                booking=booking,
                error=None,
            )
        return render_template(
            "partials/key_handling/issue_form.html",
            key=key,
            entry="booking",
            bookings=None,
            selected_booking_id=booking.id,
            booking=booking,
            linked_booking=booking,
            selected_holder_id=booking.requester_id,
            warning_booking=None,
            all_users=eligible_holders(),
            error=None,
        )

    @app.post("/key-handling/bookings/<int:booking_id>/issue")
    @role_required("OPERATOR")
    def key_handling_booking_issue(booking_id):
        booking = get_booking(booking_id)
        if booking is None:
            abort(404)
        key = resolve_key_for_booking(booking)
        if key is None:
            abort(400)

        holder_id = request.form.get("holder_id")
        identification_type = request.form.get("identification_type")
        identification_value = request.form.get("identification_value", "").strip()

        try:
            transaction = issue_key(
                key,
                holder_id=int(holder_id) if holder_id else None,
                identification_type=identification_type,
                identification_value=identification_value,
                operator_id=current_user.id,
                booking_id=booking.id,
            )
        except (ValueError, TypeError) as err:
            return render_template(
                "partials/key_handling/issue_form.html",
                entry="booking",
                booking=booking,
                linked_booking=booking,
                key=key,
                bookings=None,
                selected_booking_id=booking.id,
                selected_holder_id=int(holder_id) if holder_id else booking.requester_id,
                warning_booking=None,
                all_users=eligible_holders(),
                error=str(err),
            ), 422

        return render_template(
            "partials/key_handling/_bookings_list_oob.html",
            booking_rows=list_in_progress_and_upcoming_bookings(),
            unresolved_bookings=list_unresolved_bookings(),
        ) + render_toast("success", f"{key.tag} issued to {transaction.holder.display_name}.")

    @app.post("/key-handling/bookings/<int:booking_id>/return")
    @role_required("OPERATOR")
    def key_handling_booking_return(booking_id):
        booking = get_booking(booking_id)
        if booking is None:
            abort(404)
        key = resolve_key_for_booking(booking)
        if key is None:
            abort(400)
        transaction = get_open_transaction(key.id)
        if transaction is None:
            abort(400)

        try:
            return_key(
                transaction,
                room_condition_notes=request.form.get("room_condition_notes"),
                damage_reported="damage_reported" in request.form,
            )
        except ValueError as err:
            return render_template(
                "partials/key_handling/return_form.html",
                key=key,
                transaction=transaction,
                entry="booking",
                booking=booking,
                error=str(err),
            ), 422

        return render_template(
            "partials/key_handling/_bookings_list_oob.html",
            booking_rows=list_in_progress_and_upcoming_bookings(),
            unresolved_bookings=list_unresolved_bookings(),
        ) + render_toast("success", f"{key.tag} returned.")
