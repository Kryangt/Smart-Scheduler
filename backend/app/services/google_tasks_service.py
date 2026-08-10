from fastapi import HTTPException
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

def get_tasks_service(creds):
    return build("tasks", "v1", credentials=creds)

def get_tasks_list(creds):

    service = get_tasks_service(creds)
    tasks = service.tasks().list(
    tasklist="@default",
    showCompleted=False,
    showHidden=False
    ).execute().get("items", [])

    return tasks


def create_task(creds, user, db, title: str = None, date: str = None, due: str = None):
        
    service = get_tasks_service(creds)
    task = {
        "title": title,
        "notes": "Created from AI scheduler",
    }
    # Only send due when both date and time are provided.
    if date and due:
        task["due"] = f"{date}T{due}:00.000Z"
    try:
        created_task = service.tasks().insert(
            tasklist="@default",
            body=task
        ).execute()
        
        return created_task
    except HttpError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Google Tasks API error: {e}",
        ) from e

