import os
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from google_tasks_service import create_task, get_tasks_list
from google_events_service import get_events, create_event

load_dotenv()
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

app = FastAPI()

SCOPES = ["https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/tasks"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
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
    state = user_credentials.get("state")
    if not state:
        return JSONResponse(status_code=400, content={"error": "Missing OAuth state. Start again at /auth/login"})

    flow = Flow.from_client_secrets_file(
        "credentials.json",
        scopes=SCOPES,
        redirect_uri="http://localhost:8000/auth/callback",
        state=state,
    )

    flow.fetch_token(authorization_response=str(request.url))

    credentials = flow.credentials
    user_credentials["creds"] = credentials_to_dict(credentials)

    return RedirectResponse("http://localhost:3000/frontend.html")

@app.get("/events")
def get_events_api():
    if "creds" not in user_credentials:
        return {"error": "User not authenticated"}

    creds = Credentials(**user_credentials["creds"])
    all_events = get_events(creds)

    return {"events": all_events}

@app.get("/create-test-event")
def create_event_api(calendar: str = None, date: str = None, start: str = None, end: str = None):
    if "creds" not in user_credentials:
        return {"error": "User not authenticated"}

    if(calendar == None or date == None or start == None or end == None):
        return {"error": "No enough information"}
    
    creds = Credentials(**user_credentials["creds"])
    created_event = create_event(creds, calendar, date, start, end)

    return {"event": created_event}

@app.get("/get-tasks")
def get_tasks_list_api():
    
    if "creds" not in user_credentials:
        return {"error": "User not authenticated"}

    creds = Credentials(**user_credentials["creds"])
    tasks = get_tasks_list(creds)

    return {"Tasks": tasks}

@app.get("/create-task")
def create_task_api(title: str = None, date: str = None, due: str = None):
    if "creds" not in user_credentials:
        return {"error": "User not authenticated"}

    if title is None or title.strip() == "":
        return {"error": "Missing information"}

        creds = Credentials(**user_credentials["creds"])
        created_task = create_task(creds, date, due)

        return {"task": created_task}


def credentials_to_dict(credentials):
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
}




