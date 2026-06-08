from fastapi.responses import JSONResponse
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

    return {"Tasks": tasks}

def create_task(creds, title: str = None, date: str = None, due: str = None):
        
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
        return {"task": created_task}
    except HttpError as e:
        return JSONResponse(status_code=400, content={"error": "Google Tasks API error", "details": str(e)})

