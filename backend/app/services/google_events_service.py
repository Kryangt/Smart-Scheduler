from datetime import datetime

from fastapi import HTTPException
from googleapiclient.discovery import build

from backend.app.models.Action_Log import ActionLog  # noqa: F401
from backend.app.models.User import User  # noqa: F401
from backend.app.models.Task import Task
from backend.app.models.Scheduled_Blocks import Scheduled_Blocks


def get_calendar_service(creds):
    return build("calendar", "v3", credentials=creds)


def _to_rfc3339(value):
    if value is None:
        return None
    if value.tzinfo is None:
        local_tz = datetime.now().astimezone().tzinfo
        value = value.replace(tzinfo=local_tz)
    return value.isoformat()


def get_events(creds, end_time=None):
    service = get_calendar_service(creds)

    selected_ids = []
    page_token = None
    while True:
        params = {"pageToken": page_token} if page_token else {}
        response = service.calendarList().list(**params).execute()
        selected_ids.extend(
            calendar["id"]
            for calendar in response.get("items", [])
            if calendar.get("selected")
        )
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    all_events = []
    time_min = _to_rfc3339(datetime.now())

    for cid in selected_ids:
        page_token = None
        while True:
            params = {
                "calendarId": cid,
                "maxResults": 250,
                "singleEvents": True,
                "orderBy": "startTime",
                "timeMin": time_min,
            }

            if end_time:
                params["timeMax"] = _to_rfc3339(end_time)
            if page_token:
                params["pageToken"] = page_token

            response = service.events().list(**params).execute()
            all_events.extend(response.get("items", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break

    return {"events": all_events}


def _event_body(date, start, end, summary):
    return {
        "summary": summary or "AI Scheduled Task",
        "start": {
            "dateTime": f"{date}T{start}:00",
            "timeZone": "America/Chicago",
        },
        "end": {
            "dateTime": f"{date}T{end}:00",
            "timeZone": "America/Chicago",
        },
    }


def _persist_event_record(db, user, date, start, end, summary, estimated_duration):
    start_datetime = datetime.fromisoformat(f"{date}T{start}")
    end_datetime = datetime.fromisoformat(f"{date}T{end}")
    task_record = Task(
        user_id=user.id,
        title=summary,
        estimated_duration=estimated_duration,
        task_type="Not defined yet",
        priority=0,
        status="unfinished",
        created_time=datetime.now(),
        updated_time=datetime.now(),
        earlist_start_time=start_datetime,
        deadline=end_datetime,
    )
    db.add(task_record)
    db.flush()
    scheduled_block = Scheduled_Blocks(
        user_id=user.id,
        task_id=task_record.id,
        start_time=start_datetime,
        end_time=end_datetime,
        status="scheduled",
        created_at=datetime.now(),
    )
    db.add(scheduled_block)
    return task_record, scheduled_block


def create_event(
    creds,
    user,
    db,
    *,
    calendar: str = "primary",
    date: str,
    start: str,
    end: str,
    summary: str = "AI Scheduled Task",
    estimated_duration: float = 0,
    calendar_service=None,
    commit: bool = True,
):
    service = calendar_service or get_calendar_service(creds)
    if summary is None:
        summary = "AI Scheduled Task"
    event = _event_body(date, start, end, summary)

    created_event = service.events().insert(
        calendarId=f"{calendar}",
        body=event
    ).execute()

    task_record, scheduled_block = _persist_event_record(
        db,
        user,
        date,
        start,
        end,
        summary,
        estimated_duration,
    )
    if commit:
        db.commit()
        db.refresh(task_record)
        db.refresh(scheduled_block)

    return created_event


def create_events_batch(creds, user, db, calendar, event_specs):
    """Create independent Calendar events in batches and persist them in one DB transaction."""
    if not event_specs:
        return []

    service = get_calendar_service(creds)
    responses = {}
    failures = {}

    def collect_response(request_id, response, exception):
        index = int(request_id)
        if exception is not None:
            failures[index] = exception
        else:
            responses[index] = response

    for chunk_start in range(0, len(event_specs), 1000):
        batch = service.new_batch_http_request()
        chunk = event_specs[chunk_start:chunk_start + 1000]
        for offset, spec in enumerate(chunk):
            index = chunk_start + offset
            batch.add(
                service.events().insert(
                    calendarId=calendar or "primary",
                    body=_event_body(
                        spec["date"],
                        spec["start"],
                        spec["end"],
                        spec.get("summary"),
                    ),
                ),
                callback=collect_response,
                request_id=str(index),
            )
        batch.execute()
        if failures:
            break

    def remove_created_google_events():
        for response in responses.values():
            event_id = response.get("id") if response else None
            if event_id:
                try:
                    service.events().delete(
                        calendarId=calendar or "primary",
                        eventId=event_id,
                    ).execute()
                except Exception:
                    pass

    if failures:
        remove_created_google_events()
        raise HTTPException(
            status_code=502,
            detail=f"Google Calendar failed to create {len(failures)} event(s)",
        )

    try:
        for index, spec in enumerate(event_specs):
            _persist_event_record(
                db,
                user,
                spec["date"],
                spec["start"],
                spec["end"],
                spec.get("summary") or "AI Scheduled Task",
                spec.get("estimated_duration", 0),
            )
        db.commit()
    except Exception:
        db.rollback()
        remove_created_google_events()
        raise

    return [responses[index] for index in range(len(event_specs))]
