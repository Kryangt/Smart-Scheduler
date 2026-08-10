from fastapi.testclient import TestClient
from google.oauth2.credentials import Credentials
from types import SimpleNamespace
from unittest.mock import patch

from backend.app.database.connection import get_db
from backend.app.main import app, get_current_user

client = TestClient(app)


def fake_credentials():
    return Credentials(
        token="fake",
        refresh_token="fake",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="fake",
        client_secret="fake",
        scopes=[]
    )


@patch("backend.app.main.get_session_credentials")
@patch("backend.app.main.get_events")
def test_get_events(mock_get_events, mock_get_session_credentials):
    mock_get_session_credentials.return_value = fake_credentials()
    mock_get_events.return_value = {
        "events": [{"title": "Test Event"}]
    }

    response = client.get("/events")

    assert response.status_code == 200
    assert "events" in response.json()
    assert response.json()["events"][0]["title"] == "Test Event"


@patch("backend.app.main.get_session_credentials")
@patch("backend.app.main.create_events_batch")
def test_create_event_uses_authenticated_user_and_database(mock_batch, mock_credentials):
    fake_db = SimpleNamespace()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7)
    app.dependency_overrides[get_db] = lambda: fake_db
    mock_credentials.return_value = fake_credentials()
    mock_batch.return_value = [{"id": "event-1"}]

    try:
        response = client.post("/events", json={
            "calendar": "primary",
            "date": "2026-08-10",
            "start": "09:00",
            "end": "10:00",
        })
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["event"]["id"] == "event-1"
    assert mock_batch.call_args.args[1].id == 7
    assert mock_batch.call_args.args[2] is fake_db


@patch("backend.app.main.get_session_credentials")
@patch("backend.app.main.create_events_for_schedule")
@patch("backend.app.main.handle_task_confirmation")
def test_confirmation_uses_camel_case_request_fields(mock_handle, mock_create_events, mock_credentials):
    fake_db = SimpleNamespace()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7)
    app.dependency_overrides[get_db] = lambda: fake_db
    mock_credentials.return_value = fake_credentials()
    mock_handle.return_value = {
        "status": "scheduled",
        "schedule": {"scheduled": [], "unscheduled": []},
    }
    mock_create_events.return_value = []

    try:
        response = client.post("/task-confirmation", json={
            "decision": "yes",
            "structured_tasks": [{
                "title": "Research",
                "deadline": "2026-08-10",
                "estimated_duration_minutes": 60,
                "reason": "Prepare",
                "depends_on": [],
            }],
            "clarifyMessages": [{"id": 1, "role": "user", "content": "Plan it"}],
            "feedbackMessages": [],
        })
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "scheduled"
    assert mock_handle.call_args.kwargs["messages"][0].content == "Plan it"
    assert mock_handle.call_args.kwargs["feedback"] == []
