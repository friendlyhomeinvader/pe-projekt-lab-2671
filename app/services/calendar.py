from datetime import datetime, time, timedelta, timezone

from app.services.booking import LIVE_STATES, list_bookings_for_room

VIEW_START_HOUR = 5
VIEW_END_HOUR = 20

ROW_HEIGHT_PX = 64
DAY_HEIGHT_PX = ROW_HEIGHT_PX * (VIEW_END_HOUR - VIEW_START_HOUR)
SLOT_MINUTES = 45

STATE_STYLES = {
    "PENDING": "bg-amber-200 border border-amber-400 text-amber-900",
    "ACTIVE": "bg-green-200 border border-green-400 text-green-900",
    "NO_SHOW": "bg-red-100 border border-red-300 text-red-700",
    "FINISHED": "bg-gray-200 border border-gray-400 text-gray-600",
}

STATE_STYLES_OWN = {
    "PENDING": "bg-amber-400 border border-amber-600 text-amber-950",
    "ACTIVE": "bg-green-400 border border-green-600 text-green-950",
    "NO_SHOW": "bg-red-300 border border-red-500 text-red-950",
    "FINISHED": "bg-gray-400 border border-gray-600 text-gray-950",
}


def current_time():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _day_bounds(day_date):
    start = datetime.combine(day_date, time(VIEW_START_HOUR, 0))
    end = datetime.combine(day_date, time(VIEW_END_HOUR, 0))
    return start, end


def _pct_of_day(dt, day_start, day_end):
    return (
        (dt - day_start).total_seconds() / (day_end - day_start).total_seconds() * 100
    )


def _merge_busy_intervals(bookings, day_start, day_end):
    intervals = []
    for b in bookings:
        if b.state not in LIVE_STATES:
            continue
        s = max(b.start_date, day_start)
        e = min(b.end_date, day_end)
        if s < e:
            intervals.append((s, e))
    intervals.sort()
    merged = []
    for s, e in intervals:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def _free_gaps(day_start, day_end, busy_intervals, now):
    lower_bound = day_start
    if day_end <= now:
        return []
    if day_start < now < day_end:
        lower_bound = now
    gaps = []
    cursor = lower_bound
    for busy_start, busy_end in busy_intervals:
        if busy_start > cursor:
            gaps.append((cursor, busy_start))
        cursor = max(cursor, busy_end)
    if cursor < day_end:
        gaps.append((cursor, day_end))
    return gaps


def _clickable_blocks_in_gap(gap_start, gap_end):
    first_hour = gap_start.replace(minute=0, second=0, microsecond=0)
    if first_hour < gap_start:
        first_hour += timedelta(hours=1)
    full_hours = []
    h = first_hour
    while h + timedelta(hours=1) <= gap_end:
        full_hours.append((h, h + timedelta(hours=1)))
        h += timedelta(hours=1)

    blocks = []
    cursor = gap_start
    for h_start, h_end in full_hours:
        if h_start > cursor:
            blocks.append((cursor, h_start))
        blocks.append((h_start, h_end))
        cursor = h_end
    if cursor < gap_end:
        blocks.append((cursor, gap_end))

    return blocks


def _clickable_blocks_for_day(day_start, day_end, busy_intervals, now):
    blocks = []
    for gap_start, gap_end in _free_gaps(day_start, day_end, busy_intervals, now):
        for sub_start, sub_end in _clickable_blocks_in_gap(gap_start, gap_end):
            blocks.append((sub_start, sub_end, gap_start, gap_end))
    return blocks


def _ceil_to_5min(dt):
    discard = timedelta(
        minutes=dt.minute % 5, seconds=dt.second, microseconds=dt.microsecond
    )
    dt = dt - discard
    if discard > timedelta(0):
        dt += timedelta(minutes=5)
    return dt


def build_slot_picker(
    row_start, row_end, gap_start, gap_end, selected_start_iso, selected_slots
):
    latest_start = gap_end - timedelta(minutes=SLOT_MINUTES)

    start_options = []
    t = _ceil_to_5min(row_start)
    while t < row_end:
        if gap_start <= t <= latest_start:
            start_options.append(t)
        t += timedelta(minutes=5)

    if not start_options:
        if row_end <= latest_start:
            start_options = [row_end]
        elif gap_start <= latest_start:
            start_options = [latest_start]

    if not start_options:
        return {
            "start_options": [],
            "selected_start": None,
            "slot_options": [],
            "selected_slots": 0,
            "end_time": None,
        }

    selected_start = None
    if selected_start_iso:
        try:
            candidate = datetime.fromisoformat(selected_start_iso)
            if candidate in start_options:
                selected_start = candidate
        except ValueError:
            pass
    if selected_start is None:
        selected_start = start_options[0]

    max_slots = max(
        1, int((gap_end - selected_start).total_seconds() // (SLOT_MINUTES * 60))
    )
    slot_options = list(range(1, max_slots + 1))

    if not selected_slots or selected_slots not in slot_options:
        selected_slots = (
            slot_options[-1]
            if (selected_slots and selected_slots > slot_options[-1])
            else slot_options[0]
        )

    end_time = selected_start + timedelta(minutes=SLOT_MINUTES * selected_slots)

    return {
        "start_options": start_options,
        "selected_start": selected_start,
        "slot_options": slot_options,
        "selected_slots": selected_slots,
        "end_time": end_time,
    }


def build_week_view(room_id, week_offset, current_user_id):
    now = current_time()
    today = now.date()
    monday = today - timedelta(days=today.weekday())
    week_start_date = monday + timedelta(weeks=week_offset)
    day_dates = [week_start_date + timedelta(days=i) for i in range(5)]

    range_start, _ = _day_bounds(day_dates[0])
    _, range_end = _day_bounds(day_dates[-1])
    bookings = list_bookings_for_room(room_id, range_start, range_end)

    days = []
    for day_date in day_dates:
        day_start, day_end = _day_bounds(day_date)
        day_bookings = [
            b for b in bookings if b.start_date < day_end and b.end_date > day_start
        ]
        busy_intervals = _merge_busy_intervals(day_bookings, day_start, day_end)

        booking_blocks = []
        for b in day_bookings:
            s = max(b.start_date, day_start)
            e = min(b.end_date, day_end)
            is_own = b.requester_id == current_user_id
            booking_blocks.append(
                {
                    "top_pct": _pct_of_day(s, day_start, day_end),
                    "height_pct": _pct_of_day(e, day_start, day_end)
                    - _pct_of_day(s, day_start, day_end),
                    "style": STATE_STYLES_OWN[b.state]
                    if is_own
                    else STATE_STYLES[b.state],
                    "is_own": is_own,
                    "label": f"{b.start_date:%H:%M}–{b.end_date:%H:%M} ({b.state})",
                }
            )

        clickable = []
        for sub_start, sub_end, gap_start, gap_end in _clickable_blocks_for_day(
            day_start, day_end, busy_intervals, now
        ):
            clickable.append(
                {
                    "top_pct": _pct_of_day(sub_start, day_start, day_end),
                    "height_pct": _pct_of_day(sub_end, day_start, day_end)
                    - _pct_of_day(sub_start, day_start, day_end),
                    "row_start_iso": sub_start.isoformat(),
                    "row_end_iso": sub_end.isoformat(),
                    "gap_start_iso": gap_start.isoformat(),
                    "gap_end_iso": gap_end.isoformat(),
                }
            )

        is_past = day_date < today
        is_today = day_date == today
        if is_today:
            if now <= day_start:
                now_top_pct = None
                past_overlay_height_pct = 0.0
            elif now >= day_end:
                now_top_pct = None
                past_overlay_height_pct = 100.0
            else:
                now_top_pct = _pct_of_day(now, day_start, day_end)
                past_overlay_height_pct = now_top_pct
        else:
            now_top_pct = None
            past_overlay_height_pct = 100.0 if is_past else 0.0

        days.append(
            {
                "date": day_date,
                "label": day_date.strftime("%a %m/%d"),
                "is_past": is_past,
                "is_today": is_today,
                "now_top_pct": now_top_pct,
                "past_overlay_height_pct": past_overlay_height_pct,
                "bookings": booking_blocks,
                "clickable": clickable,
            }
        )

    return {
        "week_label": f"{day_dates[0].strftime('%b %d')} – {day_dates[-1].strftime('%b %d, %Y')}",
        "prev_week_offset": week_offset - 1,
        "next_week_offset": week_offset + 1,
        "hours": list(range(VIEW_START_HOUR, VIEW_END_HOUR)),
        "row_height_px": ROW_HEIGHT_PX,
        "day_height_px": DAY_HEIGHT_PX,
        "days": days,
    }
