from datetime import datetime, timedelta
import math

from backend.app.services.google_events_service import get_events


# TODO: Make these user-configurable.
WORK_START = 8
WORK_END = 22


#TODO: default deadline time is 23:59: 59, but also have to consider any specified deadline

def _parse_deadline(deadline_str):
    """ parse a string deadline to datetime format deadline
    Args:
        deadline_str: the date (year/month/day) of deadline in string format
    Returns:
        the datetime format of deadline with hour, minute, second
    Raises:
        ValueError: unsupported deadline format
    """
    for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            day = datetime.strptime(deadline_str, fmt)
            # Interpret a date-only deadline as end-of-day.
            return day.replace(hour=23, minute=59, second=59, microsecond=0)
        except ValueError:
            continue
    raise ValueError(f"Unsupported deadline format: {deadline_str}")



def _parse_event_time(value):

    """ parse a dictionary input time to datetime format
    Args:
        value: the disctionary format of time
    Returns:
        the datetime format
    """

    if value is None:
        return None

    if "dateTime" in value:
        return datetime.fromisoformat(value["dateTime"].replace("Z", "+00:00")).astimezone().replace(tzinfo=None)

    if "date" in value:
        return datetime.fromisoformat(value["date"])

    return None


def preprocess(tasks):
    processed_tasks = []
    latest_deadline = None

    for task in tasks:
        deadline_dt = _parse_deadline(task["deadline"])

        if latest_deadline is None or deadline_dt > latest_deadline:
            latest_deadline = deadline_dt
        
        task["deadline"] = deadline_dt
        processed_tasks.append(task)
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


def find_free_intervals(creds, latest_deadline):
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
            free_slots.append((current_time, start))

        if end > current_time:
            current_time = end

    if current_time < latest_deadline:
        while current_time < latest_deadline:
            day_end = current_time.replace(hour = WORK_END, minute = 0, second= 0, microsecond=0)

            if(day_end > latest_deadline):
                day_end = latest_deadline

            if(day_end > current_time):
                free_slots.append((current_time, day_end))
            
            current_time_start = current_time.date() + timedelta(days = 1) #current_time_start in the form YY/MM/DD
            current_time = datetime.combine(current_time_start, datetime.min.time()).replace(hour=WORK_START)
    
    free_slots.sort(key = lambda t:t[0])
    return free_slots


def _lateness_hours(deadline, slot_end):
    if slot_end <= deadline:
        return 0.0
    return (slot_end - deadline).total_seconds() / 3600.0


def schedule(creds, tasks):
    processed_tasks, latest_deadline = preprocess(tasks)
    free_intervals = find_free_intervals(creds, latest_deadline)

    scheduled = []
    unscheduled = []
    total_lateness = 0
    
    for task in processed_tasks:
        task_title = task["title"]
        task_duration = task["estimated_duration"]
        task_deadline = task["deadline"]

        free_slot = None
        slot_index = -1
        
        for i, interval in enumerate(free_intervals):
            interval_start = interval[0]
            interval_end = interval[1]
            
            task_end_time = interval_start + timedelta(minutes=task_duration * 60)
            
            if task_deadline > interval_end and task_end_time <= interval_end:
                free_slot = interval
                slot_index = i
                break

        if free_slot is None:
            unscheduled.append(task)
        else:
            start_time = free_slot[0]
            end_time = start_time + timedelta(minutes=task_duration * 60)
            
            scheduled.append({
                "title": task_title,
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "estimated_duration": task_duration * 60
            })
            
            free_intervals[slot_index] = (end_time, free_slot[1])
            
            if end_time >= free_slot[1]:
                free_intervals.pop(slot_index)

    return {
        "scheduled": scheduled,
        "unscheduled": unscheduled,
        "total_lateness": total_lateness
    }