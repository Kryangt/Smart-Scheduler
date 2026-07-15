from sqlalchemy import Column, Integer, String, DateTime, Time
from sqlalchemy.orm import relationship
from backend.app.database.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)

    email = Column(String, unique=True, nullable=False)
    google_sub = Column(String, unique = True, nullable=False)
    age = Column(Integer)
    occupation = Column(String)

    preferred_work_start_time = Column(Time)  # or Time if you prefer
    preferred_work_end_time = Column(Time)
    timezone = Column(String)

    created_at = Column(DateTime)

    # relationships
    tasks = relationship("Task", back_populates="user")
    schedule_blocks = relationship("ScheduleBlock", back_populates="user")
    action_logs = relationship("ActionLog", back_populates="user")