import json
from typing import Any, Optional
from backend.app.services.redis_client_service import RedisError, redis_client

SESSION_TTL_SECONDS = 60 * 60 * 24

def save_session(session_id: str, user_id: int, credentials: dict[str, Any]) -> None:
    session_data = {
        "user_id": user_id,
        "credentials": credentials
    }
    
    try:
        redis_client.set(
            name =f"session:{session_id}",
            value=json.dumps(session_data),
            ex = SESSION_TTL_SECONDS
        )
    except RedisError as exc:
        raise RuntimeError("Failed to save session") from exc
    
def get_session(session_id: str) -> Optional[dict[str, Any]]:
    try:
        raw_session = redis_client.get(f"session:{session_id}")
    except RedisError as exc:
        raise RuntimeError("Failed to read session") from exc
    
    if raw_session is None:
        return None
    
    return json.loads(raw_session)

def delete_session(session_id: str)-> None:
    try:
        redis_client.delete(f"session:{session_id}")
    except RedisError as exc:
        raise RuntimeError("Failed to delete session") from exc
