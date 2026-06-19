from sqlalchemy import Column, Integer, DateTime, String, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.database.base import Base


class ActionLog(Base):
    __tablename__ = "action_logs"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.id"))
    task_id = Column(Integer, ForeignKey("tasks.id"))
    schedule_block_id = Column(Integer, ForeignKey("schedule_blocks.id"))

    action_type = Column(String)
    action_timestamp = Column(DateTime)

    old_start_time = Column(DateTime, nullable=True)
    new_start_time = Column(DateTime, nullable=True)

    trigger_source = Column(String)  # user / system / google_sync

    # relationships
    user = relationship("User", back_populates="action_logs")
    task = relationship("Task", back_populates="action_logs")
    schedule_block = relationship("ScheduleBlock", back_populates="action_logs")