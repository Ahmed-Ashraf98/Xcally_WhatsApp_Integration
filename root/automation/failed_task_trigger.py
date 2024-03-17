from root.database.db_context import *
from celery.signals import task_failure
from root.models.failed_task import FailedTask


db_tables_creation()

@task_failure.connect
def handle_task_failure(sender, task_id, exception, args, kwargs, traceback, einfo, **other):
    # Store information about the failed task in the database
    global msg_type
    global body_text

    print("*"*50)
    print("Create a new record for failed tasks")
    data_obj = args[0]
    print(data_obj)
    #  [{'msg_obj': {'contact_details': {'profile': {'name': 'Ahmed Ashraf Sana Soft'}, 'wa_id': '201066632344'}, 'message_type': 'text', 'msg_is_media': False, 'message_data': {'body': 'f'}}}]
    #

    if "msg_obj" in data_obj:
        msg_type = data_obj["msg_obj"]["message_type"]
    else :
        msg_type = data_obj["message_type"]

    if msg_type == "text" and "msg_obj" in data_obj:
        body_text = data_obj["msg_obj"]["message_data"]["body"]
        body_text = body_text.replace("'", "&sq?").replace('"', "&dq?")
        data_obj["msg_obj"]["message_data"]["body"] = body_text
        print(body_text)

    elif msg_type == "text" and "msg_obj" not in data_obj:
        body_text = data_obj["message_data"]["body"]
        body_text = body_text = body_text.replace("'", "&:sq:?").replace('"', "&:dq:?")
        data_obj["message_data"]["body"] = body_text
        print(body_text)


    print("*" * 50)
    if sender.request.retries >= sender.max_retries:
        session = Session()
        failed_task = FailedTask(
            id=task_id,
            msg_type = msg_type,
            task_name=sender.name,
            args=str(data_obj),
            kwargs=str(kwargs),
            exception=str(exception)
        )
        session.add(failed_task)
        session.commit()
        session.refresh(failed_task)
        session.close()



    # if msg_type == "text" and "msg_obj" in data_obj:
    #     body_text = data_obj["msg_obj"]["message_data"]["body"]
    #     body_text = (body_text.replace("\\'", "&squo?")
    #      .replace("\'", "&squo?")
    #      .replace("'", "&squo?")
    #      .replace('\"', "&dquo?")
    #      .replace('\\"', "&dquo?")
    #      .replace('"', "&dquo?")
    #      )
    #     data_obj["msg_obj"]["message_data"]["body"] = body_text
    #     print(body_text)
    #
    # elif msg_type == "text" and "msg_obj" not in data_obj:
    #     body_text =data_obj["message_data"]["body"]
    #     body_text = (body_text.replace("\\'", "&squo?")
    #      .replace("\'", "&squo?")
    #      .replace("'", "&squo?")
    #      .replace('\"', "&dquo?")
    #      .replace('\\"', "&dquo?")
    #      .replace('"', "&dquo?")
    #      )