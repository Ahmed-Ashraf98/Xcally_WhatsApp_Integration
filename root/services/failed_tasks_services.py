import json
import time

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
                        time.sleep(30) # 0.5 minute

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
    global json_data

    """
    SQLAlchemy will usually create a column of type VARCHAR or TEXT in the underlying database.
    The JSON data you insert into this column will be stored as a string.
    """
    task_args_str = task.args
    json_string = task_args_str.replace("True", "true").replace("False", "false").replace("None", "null")

    #-----------------------------

    if task.msg_type == "text":
        body_index = task_args_str.find("body")
        # json.loads(task_args_str.replace("True", "true").replace("False", "false").replace("None", "null"))
        if body_index != -1 :
            single_quote_symbol= "&#39;"
            double_qoute_symbol = "&#34;"

            if "\\\'" in json_string : # contains sinqle qoutes inside the body and double qoutes
                valid_json_string = json_string.replace("\\\'",single_quote_symbol).replace('"',double_qoute_symbol).replace("'",'"')
                data_obj = json.loads(valid_json_string)

                if "msg_obj" in data_obj:
                    body_text = data_obj["msg_obj"]["message_data"]["body"]
                    body_text = body_text.replace(single_quote_symbol,"\'").replace(double_qoute_symbol,'"')
                    data_obj["msg_obj"]["message_data"]["body"] = body_text

                elif "msg_obj" not in data_obj:
                    body_text = data_obj["message_data"]["body"]
                    body_text = body_text.replace(single_quote_symbol, "\'").replace(double_qoute_symbol, '"')
                    data_obj["message_data"]["body"] = body_text

                json_data = data_obj

            else: # contains only sinqle qoutes inside the body without double qoutes
                body_index = json_string.find("body")
                colon_index= json_string[body_index:].find(":")

                eob_index = json_string[body_index:].find(",") # end of body

                if eob_index == -1:
                    eob_index = json_string[body_index:].find("}")

                text = json_string[body_index:][colon_index+1:eob_index]
                encoded_text = text.replace('\'', single_quote_symbol)
                clear_dp_from_text = encoded_text.replace('"',"")
                updated_text = clear_dp_from_text.strip()
                json_string = json_string.replace(json_string[body_index:][colon_index + 1:eob_index],"'"+updated_text+"'")
                valid_json_string = json_string.replace("'", '"')
                json_data = json.loads(valid_json_string)

                if "msg_obj" in json_data:
                    body_text = json_data["msg_obj"]["message_data"]["body"]
                    body_text = body_text.replace(single_quote_symbol, "\'")
                    json_data["msg_obj"]["message_data"]["body"] = body_text

                elif "msg_obj" not in json_data:
                    body_text = json_data["msg_obj"]["message_data"]["body"]
                    body_text = body_text.replace(single_quote_symbol, "\'")
                    json_data["msg_obj"]["message_data"]["body"] = body_text

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

    elif task.task_name.endswith("xc_download_attachment"):
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