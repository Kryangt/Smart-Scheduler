import os

VPN_PORT = "7897" 
os.environ["http_proxy"] = f"http://127.0.0.1:{VPN_PORT}"
os.environ["https_proxy"] = f"http://127.0.0.1:{VPN_PORT}"
os.environ["HTTP_PROXY"] = f"http://127.0.0.1:{VPN_PORT}"
os.environ["HTTPS_PROXY"] = f"http://127.0.0.1:{VPN_PORT}"

import secrets
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlsplit, urlunsplit
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
from backend.app.services.ai_assistance_service import ai_assistance_control_center
from typing import Literal, List

#database part
from backend.app.database.base import Base
from backend.app.database.connection import get_connection
from backend.app.database.connection import engine
from backend.app.models.User import User
from backend.app.models.Task import Task
from backend.app.models.Scheduled_Blocks import Scheduled_Blocks
from backend.app.models.Action_Log import ActionLog

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")

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


def is_local_redirect_uri() -> bool:
    return GOOGLE_REDIRECT_URI.startswith(("http://localhost", "http://127.0.0.1"))


if is_local_redirect_uri():
    # OAuth requires HTTPS in production. This exception is only for local dev.
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

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


def build_authorization_response(request: Request) -> str:
    redirect_uri = urlsplit(GOOGLE_REDIRECT_URI)
    return urlunsplit((
        redirect_uri.scheme,
        redirect_uri.netloc,
        redirect_uri.path,
        request.url.query,
        "",
    ))


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

class CreateEventRequest(BaseModel):
    calendar: str = "primary"
    date: str
    start: str
    end: str

class CreateTaskRequest(BaseModel):
    title: str
    date: str | None = None
    due: str | None = None

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


    authorization_response = build_authorization_response(request)
    flow.fetch_token(authorization_response=authorization_response)

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
def create_event_api(request: Request, payload: CreateEventRequest):
    creds = get_session_credentials(request)
    created_event = create_event(
        creds,
        payload.calendar,
        payload.date,
        payload.start,
        payload.end,
    )
    return {"event": created_event}

@app.get("/tasks")
def get_tasks_list_api(request: Request):
    creds = get_session_credentials(request)
    tasks = get_tasks_list(creds)

    return {"Tasks": tasks}

@app.post("/tasks")
def create_task_api(request: Request, payload: CreateTaskRequest):
    creds = get_session_credentials(request)
    created_task = create_task(
        creds,
        payload.title,
        payload.date,
        payload.due,
    )
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


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
class TaskDecompositeRequest(BaseModel):
    messages: List[ChatMessage]

@app.post("/task-decomposition")
def decompose_tasks_api(request: Request, payLoad: TaskDecompositeRequest):
    if(len(payLoad.messages) == 0):
        return {"No messages detect"}
    if(payLoad.messages[len(payLoad.messages-1)].role != "user"):
        return {"Last turn shoudld be user"}

    return ai_assistance_control_center(payLoad)

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
