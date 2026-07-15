from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from backend.app.models import Task, Scheduled_Blocks
    
from datetime import datetime

import httplib2
import google_auth_httplib2
# def get_calendar_service(creds):
#     return build("calendar", "v3", credentials=creds)


#In China, we have to use VPN
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

    cal_items = service.calendarList().list().execute().get("items", [])
    selected_ids = [c["id"] for c in cal_items if c.get("selected")]

    all_events = []
    time_min = _to_rfc3339(datetime.now())

    for cid in selected_ids:
        params = {
            "calendarId": cid,
            "maxResults": 50,
            "singleEvents": True,
            "orderBy": "startTime",
            "timeMin": time_min,
        }

        if end_time:
            params["timeMax"] = _to_rfc3339(end_time)

        resp = service.events().list(**params).execute()
        all_events.extend(resp.get("items", []))

    return {"events": all_events}

def create_event(creds, user, db, calendar: str = None, date: str = None, start: str = None, end: str = None, summary: str = None, estimated_duration: int = 0):

    service = get_calendar_service(creds)
    if summary is None:
        summary = "AI Scheduled Task"
    event = {
        "summary": summary,
        "start": {
            "dateTime": f"{date}T{start}:00",
            "timeZone": "America/Chicago",
        },
        "end": {
            "dateTime": f"{date}T{end}:00",
            "timeZone": "America/Chicago",
        },
    }

    created_event = service.events().insert(
        calendarId=f"{calendar}",
        body=event
    ).execute()

    event = Task(
        user_id=user.id,
        title=summary,
        estimated_duration=estimated_duration,
        task_type="Not defined yet",
        priority=0,
        status="unfinished",
        created_time=datetime.now(),
        updated_time=datetime.now(),
    )

    db.add(event)

    scheduled_blocks = Scheduled_Blocks(
        user_id = user.id,
        task_id = event.id,
        start_time = start,
        end_time = end,
        status = "scheduled",
        created_at = datetime.now(),
    )
    db.add(scheduled_blocks)
    db.commit()
    return {"event": created_event}
