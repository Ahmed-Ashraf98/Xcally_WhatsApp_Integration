from sqlalchemy import create_engine,MetaData,DDL
from sqlalchemy.orm import sessionmaker

from sqlalchemy.exc import OperationalError

from root.config_vars import db_path
from root.models.failed_task import Base


engine = create_engine(db_path)
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
Session.configure(bind=engine)

def db_tables_creation():
    engine = create_engine(db_path)
    Base.metadata.create_all(engine)


