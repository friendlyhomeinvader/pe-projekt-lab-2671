import os
import threading
import time
from datetime import datetime, timedelta, timezone

from app import db
from app.models.booking import Booking
from app.models.key_transaction import KeyTransaction
from app.services.audit import log_action
from app.services.booking import LIVE_STATES
from app.services.preferences import get_no_show_grace_minutes

SWEEP_INTERVAL_SECONDS = 60


def apply_no_shows(now=None):
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    threshold = now - timedelta(minutes=get_no_show_grace_minutes())
    candidates = Booking.query.filter(
        Booking.state.in_(LIVE_STATES),
        Booking.start_date <= threshold,
    ).all()

    changed = []
    for booking in candidates:
        open_transaction = KeyTransaction.query.filter_by(
            booking_id=booking.id, state="ISSUED"
        ).first()
        if open_transaction is None:
            booking.state = "NO_SHOW"
            changed.append(booking)

    if changed:
        db.session.commit()
        for booking in changed:
            log_action(
                None, "booking.no_show", entity_type="booking", entity_id=booking.id
            )
    return changed


def _sweep_loop(app):
    while True:
        with app.app_context():
            try:
                apply_no_shows()
            except Exception:
                app.logger.exception("No-show sweep failed")
        time.sleep(SWEEP_INTERVAL_SECONDS)


def start_no_show_sweeper(app):
    flask_debug = os.environ.get("FLASK_DEBUG", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    is_reloader_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    if flask_debug and not is_reloader_child:
        return None

    thread = threading.Thread(target=_sweep_loop, args=(app,), daemon=True)
    thread.start()
    return thread
