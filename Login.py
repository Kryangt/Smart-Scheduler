import os
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Store credentials temporarily (for MVP only)
user_credentials = {}

@app.get("/")
def root():
    return {"message": "Calendar AI Backend Running"}

@app.get("/auth/login")
def login():
    flow = Flow.from_client_secrets_file(
        "credentials.json",
        scopes=SCOPES,
        redirect_uri="http://localhost:8000/auth/callback"
    )

    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent"
    )

    user_credentials["state"] = state
    return RedirectResponse(auth_url)

@app.get("/auth/callback")
def callback(request: Request):
    flow = Flow.from_client_secrets_file(
        "credentials.json",
        scopes=SCOPES,
        redirect_uri="http://localhost:8000/auth/callback"
    )

    flow.fetch_token(authorization_response=str(request.url))

    credentials = flow.credentials
    user_credentials["creds"] = credentials_to_dict(credentials)

    return {"message": "Authentication successful!"}

@app.get("/events")
def get_events():
    if "creds" not in user_credentials:
        return {"error": "User not authenticated"}

    creds = Credentials(**user_credentials["creds"])
    service = build("calendar", "v3", credentials=creds)

    events_result = service.events().list(
        calendarId="primary",
        maxResults=10,
        singleEvents=True,
        orderBy="updated",
        updatedMin="2026-02-23T00:00:00Z"
    ).execute()

    events = events_result.get("items", [])
    return {"events": events}

@app.get("/create-test-event")
def create_event():
    if "creds" not in user_credentials:
        return {"error": "User not authenticated"}

    creds = Credentials(**user_credentials["creds"])
    service = build("calendar", "v3", credentials=creds)

    event = {
        "summary": "AI Scheduled Task",
        "start": {
            "dateTime": "2026-02-23T10:00:00",
            "timeZone": "America/Chicago",
        },
        "end": {
            "dateTime": "2026-02-23T11:00:00",
            "timeZone": "America/Chicago",
        },
    }

    created_event = service.events().insert(
        calendarId="primary",
        body=event
    ).execute()

    return {"event": created_event}


def credentials_to_dict(credentials):
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }
