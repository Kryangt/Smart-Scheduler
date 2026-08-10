from types import SimpleNamespace

from backend.app.services import google_events_service


class FakeRequest:
    def __init__(self, body=None):
        self.body = body


class FakeBatch:
    def __init__(self):
        self.requests = []

    def add(self, request, callback, request_id):
        self.requests.append((request, callback, request_id))

    def execute(self):
        for request, callback, request_id in self.requests:
            callback(request_id, {"id": f"event-{request_id}", "body": request.body}, None)


class FakeEvents:
    def insert(self, calendarId, body):
        return FakeRequest(body)


class FakeCalendarService:
    def __init__(self):
        self.events_resource = FakeEvents()
        self.batches = []

    def events(self):
        return self.events_resource

    def new_batch_http_request(self):
        batch = FakeBatch()
        self.batches.append(batch)
        return batch


class FakeDb:
    def __init__(self):
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, record):
        self.added.append(record)

    def flush(self):
        task_records = [record for record in self.added if record.__class__.__name__ == "Task"]
        if task_records and task_records[-1].id is None:
            task_records[-1].id = len(task_records)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_batch_event_creation_uses_one_http_batch_and_one_db_commit(monkeypatch):
    service = FakeCalendarService()
    db = FakeDb()
    monkeypatch.setattr(google_events_service, "get_calendar_service", lambda creds: service)
    specs = [
        {
            "date": "2026-08-10",
            "start": "09:00",
            "end": "10:00",
            "summary": "Task A",
            "estimated_duration": 60,
        },
        {
            "date": "2026-08-10",
            "start": "10:00",
            "end": "11:00",
            "summary": "Task B",
            "estimated_duration": 60,
        },
    ]

    result = google_events_service.create_events_batch(
        creds=None,
        user=SimpleNamespace(id=7),
        db=db,
        calendar="primary",
        event_specs=specs,
    )

    assert [event["id"] for event in result] == ["event-0", "event-1"]
    assert len(service.batches) == 1
    assert len(service.batches[0].requests) == 2
    assert db.commits == 1
    assert db.rollbacks == 0
    assert len(db.added) == 4
