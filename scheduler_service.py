from datetime import datetime, timedelta
import math

from google_events_service import get_events


# TODO: Make these user-configurable.
WORK_START = 8
WORK_END = 22

def _parse_deadline(deadline_str):
    for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            day = datetime.strptime(deadline_str, fmt)
            # Interpret a date-only deadline as end-of-day.
            return day.replace(hour=23, minute=59, second=59, microsecond=0)
        except ValueError:
            continue
    raise ValueError(f"Unsupported deadline format: {deadline_str}")


def _parse_event_time(value):
    if value is None:
        return None

    if "dateTime" in value:
        return datetime.fromisoformat(value["dateTime"].replace("Z", "+00:00")).astimezone().replace(tzinfo=None)

    if "date" in value:
        return datetime.fromisoformat(value["date"])

    return None


def preprocess(tasks):
    # TODO: Current design discretizes tasks into 1-hour units.
    processed_tasks = []
    latest_deadline = None

    for task in tasks:
        duration = float(task["estimated_duration"])
        full_hours = int(math.ceil(duration))
        deadline_dt = _parse_deadline(task["deadline"])

        if latest_deadline is None or deadline_dt > latest_deadline:
            latest_deadline = deadline_dt

        for chunk_idx in range(full_hours):
            processed_tasks.append(
                {
                    "title": task["title"],
                    "deadline": deadline_dt,
                    "estimated_duration": 1,
                    "chunk": chunk_idx + 1,
                    "chunks_total": full_hours,
                }
            )

    processed_tasks.sort(key=lambda t: t["deadline"])
    return processed_tasks, latest_deadline


def _gap_to_hour_slots(gap_start, gap_end):
    slots = []
    cursor = gap_start

    while cursor + timedelta(hours=1) <= gap_end:
        day_start = cursor.replace(hour=WORK_START, minute=0, second=0, microsecond=0)
        day_end = cursor.replace(hour=WORK_END, minute=0, second=0, microsecond=0)

        if cursor < day_start:
            cursor = day_start
            continue

        if cursor >= day_end:
            next_day = (cursor + timedelta(days=1)).replace(hour=WORK_START, minute=0, second=0, microsecond=0)
            cursor = next_day
            continue

        slot_end = min(cursor + timedelta(hours=1), day_end, gap_end)
        if slot_end - cursor == timedelta(hours=1):
            slots.append((cursor, slot_end))

        cursor = slot_end

    return slots


def find_free_slots_flat(creds, latest_deadline):
    payload = get_events(creds, end_time=latest_deadline)
    events = payload.get("events", [])

    parsed_events = []
    for event in events:
        start = _parse_event_time(event.get("start", {}))
        end = _parse_event_time(event.get("end", {}))
        if start and end and end > start:
            parsed_events.append((start, end))

    parsed_events.sort(key=lambda x: x[0])

    free_slots = []
    current_time = datetime.now().replace(minute=0, second=0, microsecond=0)

    for start, end in parsed_events:
        if end <= current_time:
            continue

        if start > current_time:
            free_slots.extend(_gap_to_hour_slots(current_time, start))

        if end > current_time:
            current_time = end

    if current_time < latest_deadline:
        free_slots.extend(_gap_to_hour_slots(current_time, latest_deadline))

    return free_slots


def _lateness_hours(deadline, slot_end):
    if slot_end <= deadline:
        return 0.0
    return (slot_end - deadline).total_seconds() / 3600.0


def schedule(creds, tasks):
    # 1) Preprocess tasks into 1-hour units.
    processed_tasks, latest_deadline = preprocess(tasks)
    if not processed_tasks:
        return {"scheduled": [], "total_lateness_hours": 0.0, "unscheduled": []}

    # 2) Find free 1-hour slots up to latest deadline.
    free_slots = find_free_slots_flat(creds, latest_deadline)
    if not free_slots:
        return {
            "scheduled": [],
            "total_lateness_hours": None,
            "unscheduled": processed_tasks,
            "message": "No available free slots before latest deadline.",
        }

    n = len(processed_tasks)
    m = len(free_slots)

    #3) Go through the dp array to calculate minimum lateness hours
    inf = float("inf")
    dp = [[inf] * (m + 1) for _ in range(n + 1)]
    choose = [[False] * (m + 1) for _ in range(n + 1)]

    for j in range(m + 1):
        dp[0][j] = 0.0

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            task = processed_tasks[i - 1]
            slot_start, slot_end = free_slots[j - 1]

            use_cost = dp[i - 1][j - 1] + _lateness_hours(task["deadline"], slot_end)
            skip_cost = dp[i][j - 1]

            if use_cost <= skip_cost:
                dp[i][j] = use_cost
                choose[i][j] = True
            else:
                dp[i][j] = skip_cost

    if dp[n][m] == inf: #happened when the most late free slot is still earlier than the deadline of the earlist task
        return {
            "scheduled": [],
            "total_lateness_hours": None,
            "unscheduled": processed_tasks,
            "message": "Not enough free slots to place all tasks.",
        }

    # Reconstruct chosen assignments.
    scheduled = []
    i, j = n, m
    while i > 0 and j > 0:
        if choose[i][j]:
            task = processed_tasks[i - 1]
            slot_start, slot_end = free_slots[j - 1]
            scheduled.append(
                {
                    "title": task["title"],
                    "chunk": f"{task['chunk']}/{task['chunks_total']}",
                    "start": slot_start.isoformat(),
                    "end": slot_end.isoformat(),
                    "deadline": task["deadline"].isoformat(),
                    "lateness_hours": round(_lateness_hours(task["deadline"], slot_end), 3),
                }
            )
            i -= 1
            j -= 1
        else:
            j -= 1

    scheduled.reverse()

    unscheduled = []
    if i > 0:
        unscheduled = processed_tasks[:i]

    return {
        "scheduled": scheduled,
        "total_lateness_hours": round(dp[n][m], 3),
        "unscheduled": unscheduled,
    }
