from root.database.db_context import *
from celery.signals import task_failure
from root.models.failed_task import FailedTask


db_tables_creation()

@task_failure.connect
def handle_task_failure(sender, task_id, exception, args, kwargs, traceback, einfo, **other):
    # Store information about the failed task in the database

    print("*"*50)
    print("Create a new record for failed tasks")
    print("*" * 50)
    if sender.request.retries >= sender.max_retries:
        session = Session()
        failed_task = FailedTask(
            id=task_id,
            task_name=sender.name,
            args=str(args),
            kwargs=str(kwargs),
            exception=str(exception)
        )
        session.add(failed_task)
        session.commit()
        session.refresh(failed_task)
        session.close()
