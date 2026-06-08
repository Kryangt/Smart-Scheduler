import os
import secrets
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv
from backend.app.services.google_tasks_service import create_task, get_tasks_list
from backend.app.services.google_events_service import get_events, create_event
from backend.app.services.scheduler_service import schedule


#database part
from app.database.base import Base
from backend.app.database.connection import get_connection
from app.database.connection import engine
from app.models.User import User
from app.models.Task import Task
from backend.app.models.Scheduled_Blocks import ScheduleBlock
from app.models.Action_Log import ActionLog

load_dotenv()

app = FastAPI()

SCOPES = ["https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/tasks"]

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://localhost:8080").rstrip("/")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", f"{BACKEND_BASE_URL}/auth/callback")
COOKIE_SECURE = GOOGLE_REDIRECT_URI.startswith("https://")
SESSION_COOKIE_NAME = "session_id"
DEFAULT_CORS_ORIGINS = [
    FRONTEND_URL,
    "http://localhost:3000",
    "http://localhost:5173",
]
oauth_state_store = {}
credential_store = {}

Base.metadata.create_all(bind=engine) #build databases first

def get_cors_origins() -> List[str]:
    configured = os.getenv("CORS_ORIGINS")
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return DEFAULT_CORS_ORIGINS


def build_google_client_config() -> Optional[dict]:
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    project_id = os.getenv("GOOGLE_PROJECT_ID")

    if client_id and client_secret:
        return {
            "web": {
                "client_id": client_id,
                "project_id": project_id,
                "auth_uri": os.getenv("GOOGLE_AUTH_URI", "https://accounts.google.com/o/oauth2/auth"),
                "token_uri": os.getenv("GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token"),
                "auth_provider_x509_cert_url": os.getenv(
                    "GOOGLE_AUTH_PROVIDER_CERT_URL",
                    "https://www.googleapis.com/oauth2/v1/certs",
                ),
                "client_secret": client_secret,
                "redirect_uris": [GOOGLE_REDIRECT_URI],
            }
        }

    credentials_path = os.getenv("GOOGLE_OAUTH_CREDENTIALS_PATH", "credentials.json")
    if os.path.exists(credentials_path):
        return credentials_path

    return None


def create_google_flow(state: Optional[str] = None) -> Flow:
    client_config = build_google_client_config()
    if not client_config:
        raise HTTPException(
            status_code=500,
            detail=(
                "Google OAuth is not configured. Set GOOGLE_CLIENT_ID and "
                "GOOGLE_CLIENT_SECRET, or provide GOOGLE_OAUTH_CREDENTIALS_PATH."
            ),
        )

    if isinstance(client_config, str):
        return Flow.from_client_secrets_file(
            client_config,
            scopes=SCOPES,
            redirect_uri=GOOGLE_REDIRECT_URI,
            state=state,
        )

    return Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=GOOGLE_REDIRECT_URI,
        state=state,
    )


def get_or_create_session_id(request: Request) -> str:
    return request.cookies.get(SESSION_COOKIE_NAME) or secrets.token_urlsafe(32)


def get_session_credentials(request: Request) -> Credentials:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    stored_creds = credential_store.get(session_id)
    if not stored_creds:
        raise HTTPException(status_code=401, detail="User not authenticated")
    return Credentials(**stored_creds)


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TaskInput(BaseModel):
    title: str
    deadline: str
    estimated_duration: float

class ScheduleRequest(BaseModel):
    tasks: List[TaskInput]
    calendar: Optional[str] = "primary"


@app.get("/")
def root():
    return {"message": "Calendar AI Backend Running"}

@app.get("/auth/login")
def login(request: Request):
    session_id = get_or_create_session_id(request)
    flow = create_google_flow()

    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent"
    )

    oauth_state_store[session_id] = state
    response = RedirectResponse(auth_url)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_id,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="none" if COOKIE_SECURE else "lax",
    )
    return response


@app.get("/auth/callback")
def callback(request: Request):
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    state = oauth_state_store.get(session_id) if session_id else None
    if not state:
        return JSONResponse(status_code=400, content={"error": "Missing OAuth state. Start again at /auth/login"})
    flow = create_google_flow(state=state)


    trusted_base = "https://smartschedule-backend-266249423936.us-central1.run.app"
    path = request.url.path
    query = request.url.query
    authorization_response = f"{trusted_base}{path}?{query}"
    flow.fetch_token(authorization_response= authorization_response)

    credentials = flow.credentials
    credential_store[session_id] = credentials_to_dict(credentials)
    oauth_state_store.pop(session_id, None)

    return RedirectResponse(FRONTEND_URL)


@app.get("/events")
def get_events_api(request: Request):
    creds = get_session_credentials(request)
    all_events = get_events(creds)

    return {"events": all_events}

@app.post("/events")
def create_event_api(request: Request, calendar: str = None, date: str = None, start: str = None, end: str = None):
    if(calendar == None or date == None or start == None or end == None):
        return {"error": "No enough information"}
    
    creds = get_session_credentials(request)
    created_event = create_event(creds, calendar, date, start, end)

    return {"event": created_event}

@app.get("/tasks")
def get_tasks_list_api(request: Request):
    creds = get_session_credentials(request)
    tasks = get_tasks_list(creds)

    return {"Tasks": tasks}

@app.post("/tasks")
def create_task_api(request: Request, title: str = None, date: str = None, due: str = None):
    if title is None or title.strip() == "":
        return {"error": "Missing information"}

    creds = get_session_credentials(request)
    created_task = create_task(creds, title, date, due)

    return {"task": created_task}

@app.post("/scheduledtasks")
def schedule_tasks_api(request: Request, payload: ScheduleRequest):
    creds = get_session_credentials(request)
    tasks = [task.model_dump() for task in payload.tasks]
    schedule_result = schedule(creds, tasks)

    created_events = []
    for item in schedule_result.get("scheduled", []):
        start_dt = datetime.fromisoformat(item["start"])
        end_dt = datetime.fromisoformat(item["end"])
        date = start_dt.date().isoformat()
        start_time = start_dt.strftime("%H:%M")
        end_time = end_dt.strftime("%H:%M")
        summary = item.get("title", "AI Scheduled Task")
        chunk = item.get("chunk")
        if chunk:
            summary = f"{summary} ({chunk})"

        created_event = create_event(
            creds,
            payload.calendar or "primary",
            date,
            start_time,
            end_time,
            summary=summary
        )
        created_events.append(created_event)

    return {"schedule": schedule_result, "created_events": created_events}

@app.post("/upload")
def pdf_file_upload_api():
    #TODO: pass the file to AI and divide sub-tasks and determine time needed for each sub tasks
    return {"file upload success"}

@app.get("/test-db")
def test_db_api():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT NOW();")
    result = cur.fetchone()

    cur.close()
    conn.close()

    return {"time": str(result[0])}

def credentials_to_dict(credentials):
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
}


