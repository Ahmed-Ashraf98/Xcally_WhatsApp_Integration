import json
from root.services import xcally_services as xc_services
from root.services import whatsapp_services as wa_services
from root.celery import celery
from celery import chain
from root.automation.failed_task_trigger import *
import re


@celery.task
def failed_tasks_handler():
    # Create a session
    print("------ Starting Failed Tasks ---------------")
    try:
        with Session() as session:
            # Fetch data from the 'failed_tasks' table
            failed_tasks = session.query(FailedTask).all()

            print("="*50)
            for task in failed_tasks:
                print("Start Task : ")
                print(task.id)
                chain_task = generate_chain_task_for_faild_task(task)
                print("chain task created")
                if chain_task is None:
                    print("No such task")
                    continue
                print("="*50)
                print("Waiting Results")
                task_obj = chain_task.apply_async(queue="failed_tasks")
                try:
                    print("Trying task")
                    while task_obj.status == "PENDING":
                        print("Waiting result .........")
                    if task_obj.status == "SUCCESS":
                        on_success_for_failed_tasks(task.id)
                    print(task_obj)
                except Exception as exc :
                    on_error_for_failed_tasks(task.id, exception=exc)
            # Close the session
            session.close()
    except Exception as e:
        print("Error:>>>", e)


def on_error_for_failed_tasks(record_task_id, exception):
    print(f"Error callback triggered: {exception}")
    # delete old task record
    delete_task_record(record_task_id)


def on_success_for_failed_tasks(record_task_id):
    print(f"Success callback triggered")
    # delete old task record
    delete_task_record(record_task_id)


def generate_chain_task_for_faild_task(task):

    global task_sig
    global valid_json_string
    """
    SQLAlchemy will usually create a column of type VARCHAR or TEXT in the underlying database.
    The JSON data you insert into this column will be stored as a string.
    """
    task_args_str = task.args

    #-----------------------------
    # task_args_str.replace("'","\'").replace('"','\\"')
    if task.msg_type == "text":

        body_index = task_args_str.find("body")

        if body_index != -1 :
            valid_json_string = task_args_str.replace("'",'"').replace("False", "false").replace("True", "true").replace("None", "null")
            valid_json_string = valid_json_string.replace("&:sq:?","'")
            valid_json_string = valid_json_string.replace("&:dq:?",'\\"')
    else:
        valid_json_string = task_args_str.replace("'", '"').replace("False", "false").replace("True", "true").replace("None", "null")

    json_data = json.loads(valid_json_string)

    # -----------------------------

    task_args_obj = json_data

    print("Task is ")
    print(task_args_obj)

    if task.task_name.endswith("wa_get_media_details"):

        task_sig = chain(wa_services.wa_get_media_details.s(task_args_obj).set(queue='failed_tasks'),
                         wa_services.wa_download_media.s().set(queue='failed_tasks'),
                         xc_services.xc_upload_attachment.s().set(queue='failed_tasks'),
                         xc_services.send_message_to_xcally_channel.s().set(queue='failed_tasks'))

    elif task.task_name.endswith("wa_download_media"): # the url of the download expired, and you want to start again
        task_sig = chain(wa_services.wa_get_media_details.s(task_args_obj["msg_obj"]).set(queue='failed_tasks'),
                         wa_services.wa_download_media.s().set(queue='failed_tasks'),
                         xc_services.xc_upload_attachment.s().set(queue='failed_tasks'),
                         xc_services.send_message_to_xcally_channel.s().set(queue='failed_tasks'))

    elif task.task_name.endswith("xc_upload_attachment"):
        task_sig = chain(xc_services.xc_upload_attachment.s(task_args_obj).set(queue='failed_tasks'),
                         xc_services.send_message_to_xcally_channel.s().set(queue='failed_tasks'))

    elif task.task_name.endswith("send_message_to_xcally_channel"):
        task_sig = chain(xc_services.send_message_to_xcally_channel.s(task_args_obj).set(queue='failed_tasks'))

    elif task.task_name.endswith("xc_get_attachment_details"):
        task_sig = chain(xc_services.xc_get_attachment_details.s(task_args_obj).set(queue='failed_tasks'),
                         xc_services.xc_download_attachment.s().set(queue='failed_tasks'),
                         wa_services.wa_upload_media_handler.s().set(queue='failed_tasks'),
                         wa_services.wa_send_message_to_whatsapp_user.s().set(queue='failed_tasks'))

    elif task.task_name.endswith("xc_download_attachment"):  # the url of the download expired, and you want to start again
        task_sig = chain(xc_services.xc_download_attachment.s(task_args_obj).set(queue='failed_tasks'),
                         wa_services.wa_upload_media_handler.s().set(queue='failed_tasks'),
                         wa_services.wa_send_message_to_whatsapp_user.s().set(queue='failed_tasks'))

    elif task.task_name.endswith("wa_upload_media_handler"):
        task_sig = chain(wa_services.wa_upload_media_handler.s(task_args_obj).set(queue='failed_tasks'),
                         wa_services.wa_send_message_to_whatsapp_user.s().set(queue='failed_tasks'))

    elif task.task_name.endswith("wa_send_message_to_whatsapp_user"):
        task_sig = chain(wa_services.wa_send_message_to_whatsapp_user.s(task_args_obj).set(queue='failed_tasks'))

    else:
        return None

    print("The Sig is")
    print(task_sig)

    return task_sig


def delete_task_record(task_id):
    session = Session()
    task_to_delete = session.query(FailedTask).filter_by(id=task_id).first()
    if task_to_delete:
        session.delete(task_to_delete)
        session.commit()
        print("Task deleted successfully")
    else:
        print("Task not found")





      # sub_content = task_args_str[body_index::]
      #       if "\\'" in sub_content:
      #           separator_index = sub_content.find(",")
      #           if separator_index == -1:
      #               separator_index=sub_content.find("}")
      #           body_txt = sub_content[:separator_index]
      #           txt = body_txt[body_txt.find('"'):]
      #           txt = txt.replace("\'","\\'")
      #           indexofDB = body_txt.find('"')
      #           body_txt = body_txt.replace(body_txt[indexofDB:],txt)
      #           formatted_body = sub_content.replace(sub_content[:separator_index],body_txt)
      #           task_args_str = task_args_str.replace(task_args_str[body_index::],formatted_body)
      #



    # Replace single quotes with double quotes to make it valid JSON
    #
    # # Define a regex pattern to match single quotes not enclosed within double quotes
    # pattern = r"'(?=(?:[^\"\\\\]*(?:\\\\.|\"(?:[^\"\\\\]*(?:\\\\.|\")*)*\")*)*$)"
    #
    # # Replace the single quotes not enclosed within double quotes with a different character
    # modified_json_string = re.sub(pattern, '"', task_args_str)
    #
    # valid_json_string = modified_json_string.replace("False", "false").replace("True", "true").replace("None", "null")
    # stringfy_json = json.dumps(valid_json_string)
    # json_data = json.loads(stringfy_json)
    # last_parsing = json.loads(json_data)