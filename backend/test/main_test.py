from fastapi.testclient import TestClient
from google.oauth2.credentials import Credentials
from unittest.mock import patch

from backend.app.main import app

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
    mock_get_events.return_value = [
        {"title": "Test Event"}
    ]

    response = client.get("/events")

    assert response.status_code == 200
    assert "events" in response.json()
    assert response.json()["events"][0]["title"] == "Test Event"