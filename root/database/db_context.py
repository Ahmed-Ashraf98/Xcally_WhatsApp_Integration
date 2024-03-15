from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from root.global_vars import db_path
from root.models.failed_task import Base


engine = create_engine(db_path)
Session = sessionmaker(bind=engine)
Session.configure(bind=engine)

def db_tables_creation():
    engine = create_engine(db_path)
    Base.metadata.create_all(engine)


