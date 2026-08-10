import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlsplit, urlunsplit
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from dotenv import load_dotenv
from backend.app.services.google_tasks_service import create_task, get_tasks_list
from backend.app.services.google_events_service import create_events_batch, get_events
from backend.app.services.scheduler_service import schedule
from backend.app.services.ai_assistance_service import ai_assistance_control_center, handle_task_confirmation
from typing import Literal, List, Any

#database part
from backend.app.database.connection import get_connection, get_db
from backend.app.models.User import User
from backend.app.models.Task import Task
from sqlalchemy.orm import Session
from sqlalchemy import select
BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")

outbound_proxy = os.getenv("OUTBOUND_HTTP_PROXY")
if outbound_proxy:
    for proxy_variable in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
        os.environ[proxy_variable] = outbound_proxy

#Redis database
from backend.app.services.session_service import save_session, get_session

app = FastAPI()

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
]
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

def is_local_redirect_uri() -> bool:
    return GOOGLE_REDIRECT_URI.startswith(("http://localhost", "http://127.0.0.1"))


if is_local_redirect_uri():
    # OAuth requires HTTPS in production. This exception is only for local dev.
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

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
    session_data = get_session_data(request)

    stored_creds = session_data.get("credentials")
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

def get_session_data(request: Request) -> dict[str, Any]:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)

    if not session_id:
        raise HTTPException(
            status_code=401,
            detail="User not authenticated",
        )

    session_data = get_session(session_id)

    if not session_data:
        raise HTTPException(
            status_code=401,
            detail="Session expired or invalid",
        )

    return session_data

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    session_data = get_session_data(request)

    user_id = session_data.get("user_id")

    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="No user is associated with this session",
        )

    user = db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="User not found",
        )

    return user

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
    priority: Literal["high", "medium", "low"] = "medium"
    depends_on: list[str] = Field(default_factory=list)

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


def create_events_for_schedule(
    creds,
    user: User,
    db: Session,
    calendar: str,
    schedule_result: dict,
):
    scheduled_items = schedule_result.get("scheduled", [])
    if not scheduled_items:
        return []

    event_specs = []
    for item in scheduled_items:
        start_dt = datetime.fromisoformat(item["start"])
        end_dt = datetime.fromisoformat(item["end"])
        event_specs.append({
            "date": start_dt.date().isoformat(),
            "start": start_dt.strftime("%H:%M"),
            "end": end_dt.strftime("%H:%M"),
            "summary": item.get("title", "AI Scheduled Task"),
            "estimated_duration": item.get("estimated_duration", 0),
        })

    return create_events_batch(
        creds,
        user,
        db,
        calendar or "primary",
        event_specs,
    )

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


@app.get("/auth/status")
def auth_status(user: User = Depends(get_current_user)):
    """Return the signed-in state without making a Google API request."""
    return {
        "authenticated": True,
        "user": {
            "name": user.name,
            "email": user.email,
        },
    }


@app.get("/auth/callback")
def callback(request: Request, db: Session = Depends(get_db)):
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    returned_state = request.query_params.get("state")

    expected_state = (
        oauth_state_store.get(session_id)
        if session_id
        else None
    )
    if not expected_state or returned_state != expected_state:
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state"
        )
    
    flow = create_google_flow(state=returned_state)

    authorization_response = build_authorization_response(request)
    flow.fetch_token(authorization_response=authorization_response)

    credentials = flow.credentials

    if not credentials.id_token:
        raise HTTPException(
            status_code=400,
            detail="Google did not return an ID token",
        )

    #return identity that is readble and can access
    try:
        google_identity = id_token.verify_oauth2_token(
            credentials.id_token,
            google_requests.Request(),
            credentials.client_id,
        ) 
    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid Google identity token",
        ) from exc
    
    google_sub = google_identity.get("sub")
    email = google_identity.get("email")
    name = google_identity.get("name")

    if not google_sub or not email:
        raise HTTPException(
            status_code=400,
            detail="Google identity information is incomplete",
        )
    
    user = db.query(User).filter(User.google_sub == google_sub).first()

    if user is None:
        user = User(
            google_sub=google_sub,
            email=email,
            name=name,
        )

        db.add(user)
    else:
        user.email = email
        user.name = name
    
    db.commit()
    db.refresh(user)

    save_session(
        session_id=session_id,
        user_id=user.id,
        credentials=credentials_to_dict(credentials),
    )
    response = RedirectResponse(
        url=FRONTEND_URL,
        status_code=302,
    )

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )

    return response

def _events_retrive(userId, db_session):
    """Return a user's scheduled database tasks in the frontend event format."""
    stmt = (
        select(Task)
        .where(
            Task.user_id == userId,
            Task.earlist_start_time.is_not(None),
            Task.deadline.is_not(None),
        )
        .order_by(Task.earlist_start_time)
    )
    tasks = db_session.scalars(stmt).all()
    priority_labels = {0: "high", 1: "medium", 2: "low"}

    return {
        "events": [
            {
                "id": f"database-task-{task.id}",
                "summary": task.title or "Untitled task",
                "start": {
                    "dateTime": task.earlist_start_time.isoformat(),
                },
                "end": {
                    "dateTime": task.deadline.isoformat(),
                },
                "priority": priority_labels.get(task.priority, "medium"),
                "source": "database",
                "status": task.status,
                "estimated_duration": task.estimated_duration,
            }
            for task in tasks
        ]
    }

@app.get("/initial")
def initialization(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    events = _events_retrive(user.id, db)
    return events

@app.get("/events")
def get_events_api(request: Request):
    creds = get_session_credentials(request)
    return get_events(creds)

@app.post("/events")
def create_event_api(
    request: Request,
    payload: CreateEventRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    creds = get_session_credentials(request)
    created_event = create_events_batch(
        creds,
        user,
        db,
        payload.calendar,
        [{
            "date": payload.date,
            "start": payload.start,
            "end": payload.end,
            "summary": "AI Scheduled Task",
            "estimated_duration": 0,
        }],
    )[0]
    return {"event": created_event}

@app.get("/tasks")
def get_tasks_list_api(request: Request):
    creds = get_session_credentials(request)
    tasks = get_tasks_list(creds)

    return {"Tasks": tasks}

@app.post("/tasks")
def create_task_api(request: Request, payload: CreateTaskRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    creds = get_session_credentials(request)
    created_task = create_task(
        creds,
        user,
        db,
        payload.title,
        payload.date,
        payload.due,
    )
    return {"task": created_task}

@app.post("/scheduledtasks")
def schedule_tasks_api(request: Request, payload: ScheduleRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    creds = get_session_credentials(request)
    tasks = [task.model_dump() for task in payload.tasks]
    schedule_result = schedule(creds, tasks)

    created_events = create_events_for_schedule(
        creds,
        user,
        db,
        payload.calendar or "primary",
        schedule_result,
    )

    return {"schedule": schedule_result, "created_events": created_events}

@app.post("/upload")
def pdf_file_upload_api():
    #TODO: pass the file to AI and divide sub-tasks and determine time needed for each sub tasks
    return {"file upload success"}


class ChatMessage(BaseModel):
    id: int
    role: Literal["user", "assistant", "system"]
    content: str
class TaskDecompositeRequest(BaseModel):
    clarifyMessages: list[ChatMessage]
    feedbackMessages: list[ChatMessage] = Field(default_factory=list)

@app.post("/task-decomposition")
def decompose_tasks_api(request: Request, payLoad: TaskDecompositeRequest):
    messages = payLoad.clarifyMessages

    if len(messages) == 0:
        return {"error": "No messages detected"}

    if messages[-1].role != "user":
        return {"error": "Last turn should be user"}

    return ai_assistance_control_center(messages)

class StructuredTask(BaseModel):
    title: str
    deadline: str
    estimated_duration_minutes: int | None
    reason: str
    depends_on: list[str]
    priority: Literal["high", "medium", "low"] = "medium"


class TaskConfirmationRequest(BaseModel):
    decision: Literal["yes", "no"]
    structured_tasks: list[StructuredTask]
    clarifyMessages: list[ChatMessage] = Field(default_factory=list)
    feedbackMessages: list[ChatMessage] = Field(default_factory=list)

@app.post("/task-confirmation")
def confirm_tasks_api(
    request: Request,
    payload: TaskConfirmationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    credentials = get_session_credentials(request)

    result = handle_task_confirmation(
        cred=credentials,
        decision=payload.decision,
        messages=payload.clarifyMessages,
        structured_tasks=payload.structured_tasks,
        feedback=payload.feedbackMessages,
    )
    if payload.decision == "yes" and "schedule" in result:
        result["created_events"] = create_events_for_schedule(
            credentials,
            user,
            db,
            "primary",
            result["schedule"],
        )
    return result

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
