from celery.schedules import crontab
from root.celery import celery
from root.services.failed_tasks_services import failed_tasks_handler

@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Execute every 15 minutes.
    print("-------------- SC Task Starts ----------------------------")
    sender.add_periodic_task(crontab(minute='*/15'),failed_tasks_handler.s(),name="Check Failed Tasks")

