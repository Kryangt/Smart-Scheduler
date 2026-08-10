from datetime import datetime, time, timedelta
import heapq

from backend.app.services.google_events_service import get_events


# TODO: Make these user-configurable.
WORK_START = 8
WORK_END = 22
LATE_SCHEDULING_DAYS = 30
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _parse_deadline(deadline_value):
    if isinstance(deadline_value, datetime):
        return deadline_value

    for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            day = datetime.strptime(deadline_value, fmt)
            return day.replace(hour=23, minute=59, second=59, microsecond=0)
        except (TypeError, ValueError):
            continue

    try:
        return datetime.fromisoformat(deadline_value.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"Unsupported deadline format: {deadline_value}") from exc


def _parse_event_time(value):
    if value is None:
        return None
    if "dateTime" in value:
        return datetime.fromisoformat(value["dateTime"].replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
    if "date" in value:
        return datetime.fromisoformat(value["date"])
    return None


def _task_sort_key(task):
    return (
        task["deadline"],
        PRIORITY_ORDER.get(str(task.get("priority", "medium")).lower(), 1),
        task["_input_order"],
    )


def _order_by_dependencies(tasks):
    title_to_index = {}
    for index, task in enumerate(tasks):
        title_to_index.setdefault(task["title"], index)

    indegree = [0] * len(tasks)
    dependents = [[] for _ in tasks]
    for index, task in enumerate(tasks):
        dependency_indices = {
            title_to_index[dependency]
            for dependency in task["depends_on"]
            if dependency in title_to_index
        }
        indegree[index] = len(dependency_indices)
        for dependency_index in dependency_indices:
            dependents[dependency_index].append(index)

    ready = []
    for index, task in enumerate(tasks):
        if indegree[index] == 0:
            heapq.heappush(ready, (*_task_sort_key(task), index))

    ordered = []
    processed_indices = set()
    while ready:
        *_, index = heapq.heappop(ready)
        ordered.append(tasks[index])
        processed_indices.add(index)
        for dependent_index in dependents[index]:
            indegree[dependent_index] -= 1
            if indegree[dependent_index] == 0:
                heapq.heappush(
                    ready,
                    (*_task_sort_key(tasks[dependent_index]), dependent_index),
                )

    cyclic_tasks = []
    for index, task in enumerate(tasks):
        if index not in processed_indices:
            task["_dependency_cycle"] = True
            cyclic_tasks.append(task)
    ordered.extend(sorted(cyclic_tasks, key=_task_sort_key))

    return ordered


def preprocess(tasks):
    processed_tasks = []
    latest_deadline = None

    for input_order, task in enumerate(tasks):
        processed_task = dict(task)
        processed_task["deadline"] = _parse_deadline(processed_task["deadline"])
        processed_task["estimated_duration"] = float(processed_task["estimated_duration"])
        if processed_task["estimated_duration"] <= 0:
            raise ValueError("estimated_duration must be greater than zero")

        processed_task["priority"] = str(processed_task.get("priority", "medium")).lower()
        processed_task["depends_on"] = list(processed_task.get("depends_on") or [])
        processed_task["_input_order"] = input_order
        processed_task["_dependency_cycle"] = False
        processed_tasks.append(processed_task)

        if latest_deadline is None or processed_task["deadline"] > latest_deadline:
            latest_deadline = processed_task["deadline"]

    return _order_by_dependencies(processed_tasks), latest_deadline


def _merged_busy_intervals(events):
    parsed_events = []
    for event in events:
        start = _parse_event_time(event.get("start", {}))
        end = _parse_event_time(event.get("end", {}))
        if start and end and end > start:
            parsed_events.append((start, end))

    parsed_events.sort(key=lambda interval: interval[0])
    merged = []
    for start, end in parsed_events:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def find_free_intervals(creds, schedule_end):
    payload = get_events(creds, end_time=schedule_end)
    busy_intervals = _merged_busy_intervals(payload.get("events", []))
    now = datetime.now().replace(second=0, microsecond=0)
    free_intervals = []
    current_date = now.date()

    while datetime.combine(current_date, time.min) <= schedule_end:
        work_start = datetime.combine(current_date, time(hour=WORK_START))
        work_end = datetime.combine(current_date, time(hour=WORK_END))
        window_start = max(work_start, now)
        window_end = min(work_end, schedule_end)

        if window_start < window_end:
            cursor = window_start
            for busy_start, busy_end in busy_intervals:
                if busy_end <= window_start:
                    continue
                if busy_start >= window_end:
                    break
                clipped_start = max(busy_start, window_start)
                clipped_end = min(busy_end, window_end)
                if clipped_start > cursor:
                    free_intervals.append((cursor, clipped_start))
                cursor = max(cursor, clipped_end)
                if cursor >= window_end:
                    break
            if cursor < window_end:
                free_intervals.append((cursor, window_end))

        current_date += timedelta(days=1)

    return free_intervals


def _lateness_hours(deadline, slot_end):
    if slot_end <= deadline:
        return 0.0
    return (slot_end - deadline).total_seconds() / 3600.0


def _find_slot(free_intervals, duration, deadline, earliest_start):
    late_candidate = None

    for index, (interval_start, interval_end) in enumerate(free_intervals):
        start = max(interval_start, earliest_start)
        end = start + duration
        if end > interval_end:
            continue
        if end <= deadline:
            return index, start, end
        if late_candidate is None:
            late_candidate = (index, start, end)

    return late_candidate


def _consume_interval(free_intervals, index, start, end):
    interval_start, interval_end = free_intervals[index]
    replacement = []
    if interval_start < start:
        replacement.append((interval_start, start))
    if end < interval_end:
        replacement.append((end, interval_end))
    free_intervals[index:index + 1] = replacement


def _public_task(task, reason=None):
    result = {
        key: value
        for key, value in task.items()
        if not key.startswith("_")
    }
    result["deadline"] = task["deadline"].isoformat()
    if reason:
        result["reason"] = reason
    return result


def schedule(creds, tasks):
    processed_tasks, latest_deadline = preprocess(tasks)
    if not processed_tasks:
        return {
            "scheduled": [],
            "unscheduled": [],
            "total_lateness": 0.0,
            "deadline_misses": 0,
        }

    schedule_end = max(latest_deadline, datetime.now()) + timedelta(days=LATE_SCHEDULING_DAYS)
    free_intervals = find_free_intervals(creds, schedule_end)
    known_titles = {task["title"] for task in processed_tasks}
    completion_times = {}
    scheduled = []
    unscheduled = []
    total_lateness = 0.0
    deadline_misses = 0

    for task in processed_tasks:
        dependencies = [dependency for dependency in task["depends_on"] if dependency in known_titles]
        if task["_dependency_cycle"]:
            unscheduled.append(_public_task(task, "dependency_cycle"))
            continue
        if any(dependency not in completion_times for dependency in dependencies):
            unscheduled.append(_public_task(task, "dependency_unscheduled"))
            continue

        earliest_start = max(
            [datetime.now(), *[completion_times[dependency] for dependency in dependencies]]
        )
        duration = timedelta(hours=task["estimated_duration"])
        slot = _find_slot(free_intervals, duration, task["deadline"], earliest_start)
        if slot is None:
            unscheduled.append(_public_task(task, "no_available_interval"))
            continue

        slot_index, start_time, end_time = slot
        _consume_interval(free_intervals, slot_index, start_time, end_time)
        completion_times[task["title"]] = end_time
        lateness = _lateness_hours(task["deadline"], end_time)
        total_lateness += lateness
        if lateness > 0:
            deadline_misses += 1

        scheduled.append({
            "title": task["title"],
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "deadline": task["deadline"].isoformat(),
            "estimated_duration": task["estimated_duration"] * 60,
            "priority": task["priority"],
            "depends_on": task["depends_on"],
            "lateness_hours": lateness,
        })

    return {
        "scheduled": scheduled,
        "unscheduled": unscheduled,
        "total_lateness": total_lateness,
        "deadline_misses": deadline_misses,
    }
