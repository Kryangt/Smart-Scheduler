from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from backend.app.database.base import Base
from sqlalchemy.orm import relationship

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.id"))

    title = Column(String)
    earlist_start_time = Column(DateTime)
    deadline = Column(DateTime)
    estimated_duration = Column(Float) #In terms of Minutes
    task_type = Column(String)
    priority = Column(Integer)
    status = Column(String)
    created_time = Column(DateTime)
    updated_time = Column(DateTime)

    user = relationship("User", back_populates="tasks") #given a task, return all users objects related to this task, need to define foriegn keys
    schedule_blocks = relationship("ScheduleBlock", back_populates="task")
    action_logs = relationship("ActionLog", back_populates="task")