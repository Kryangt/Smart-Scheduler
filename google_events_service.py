from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

def get_calendar_service(creds):
    return build("calendar", "v3", credentials=creds)

def get_events(creds):
    service = get_calendar_service(creds)

    cal_items = service.calendarList().list().execute().get("items", [])
    selected_ids = [c["id"] for c in cal_items if c.get("selected")]

    all_events = []
    for cid in selected_ids:
        resp = service.events().list(
            calendarId=cid,
            maxResults=10,
            orderBy="updated"
        ).execute()
        all_events.extend(resp.get("items", []))

    return {"events": all_events}

def create_event(creds,calendar: str = None, date: str = None, start: str = None, end: str = None):

    service = get_calendar_service(creds)
    event = {
        "summary": "AI Scheduled Task",
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

    return {"event": created_event}
