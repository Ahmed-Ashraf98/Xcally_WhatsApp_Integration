from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from root.models.failed_task import Base, FailedTask


engine = create_engine('sqlite:///failed_tasks_db.db')
Session = sessionmaker(bind=engine)
Session.configure(bind=engine)

def db_tables_creation():
    engine = create_engine('sqlite:///failed_tasks_db.db')
    Base.metadata.create_all(engine)


# Base = declarative_base()
# Session = None
# def db_initialization():
#     engine = create_engine('sqlite:///failed_tasks_db.db')
#     Session = sessionmaker(bind=engine)
#     Session.configure(bind=engine)
#
#     return Session
#
# def db_tables_creation():
#     engine = create_engine('sqlite:///failed_tasks_db.db')
#     Base.metadata.create_all(engine)



