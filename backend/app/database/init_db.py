"""Explicit database initialization for local development.

Run with: python -m backend.app.database.init_db
Production deployments should use versioned migrations instead.
"""

from backend.app.database.base import Base
from backend.app.database.connection import get_migration_engine

# Import every model so SQLAlchemy registers all tables and relationships.
from backend.app.models.Action_Log import ActionLog  # noqa: F401
from backend.app.models.Scheduled_Blocks import Scheduled_Blocks  # noqa: F401
from backend.app.models.Task import Task  # noqa: F401
from backend.app.models.User import User  # noqa: F401


def init_db() -> None:
    Base.metadata.create_all(bind=get_migration_engine())


if __name__ == "__main__":
    init_db()
