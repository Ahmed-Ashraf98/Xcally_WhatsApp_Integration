from sqlalchemy.ext.declarative import declarative_base
import datetime
from sqlalchemy import Column, String, DateTime, JSON

Base = declarative_base()
class FailedTask(Base):

    __tablename__ = 'failed_tasks'

    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, default=datetime.datetime.now)
    task_name = Column(String)
    args = Column(JSON)
    kwargs = Column(String)
    exception = Column(String)


