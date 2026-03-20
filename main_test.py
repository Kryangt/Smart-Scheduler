from fastapi.testclient import TestClient
from main import app, user_credentials
from unittest.mock import patch

client = TestClient(app)

#PyTest will call the function in the beginning
def setup_module():
    user_credentials["creds"] = {
        "token": "fake",
        "refresh_token": "fake",
        "token_uri": "fake",
        "client_id": "fake",
        "client_secret": "fake",
        "scopes": []
    }

@patch("main.get_events")
def test_get_events(mock_get_events):
    mock_get_events.return_value = [{"title": "Test Event"}]
    response = client.get("/events")

    assert response.status_code == 200 
    assert "events" in response.json()
    assert response.json()["events"][0]["title"] == "Test Event"