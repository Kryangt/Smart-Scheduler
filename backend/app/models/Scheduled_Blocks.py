from sqlalchemy import Column, Integer, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship
from app.database.base import Base


class Scheduled_Blocks(Base):
    __tablename__ = "schedule_blocks"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    task_id = Column(Integer, ForeignKey("tasks.id"))

    start_time = Column(DateTime)
    end_time = Column(DateTime)

    status = Column(String)  # scheduled / canceled / moved

    created_at = Column(DateTime)

    # relationships
    user = relationship("User", back_populates="schedule_blocks")
    task = relationship("Task", back_populates="schedule_blocks")
    action_logs = relationship("ActionLog", back_populates="schedule_block")