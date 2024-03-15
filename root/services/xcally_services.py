import json
from typing import Any
from root.celery import celery
from celery import chain
from root.global_vars import *
import httpx
import os
from root.services import whatsapp_services as wa_services
import logging
from root.services.failed_task_trigger import *

client = httpx.Client(verify=False)

max_retries_for_tasks = 3
tasks_retry_delay = 10

"""
  *********  Process from receiving the message from XCally to WA ( in case the message type is media ) *******

    1) Get Attachment Details => xc_get_attachment_details

    2) Get Attachment Ttype Extension => xc_get_attachment_type_extension

    3) Download the Attachment => xc_download_attachment

    4) Upload the Attachment => wa_upload_media_handler

    5) Send the message to WA => wa_send_message_to_whatsapp_user
 ==================================================================================================================

  *********  Process from receiving the message from XCally to WA ( in case the message type is text ) *******

    1)  Send the message to WA => wa_send_message_to_whatsapp_user

 ==================================================================================================================
"""

if not os.path.exists(meta_xcally_logs_dir_path):
    os.makedirs(meta_xcally_logs_dir_path)

formatter = logging.Formatter('[ %(asctime)s ] - Code Line : [ %(lineno)d ] - %(name)s - %(levelname)s - %(message)s')

error_logger = logging.getLogger(__name__)
error_fh = logging.FileHandler(xcally_logs_path)
error_fh.setFormatter(formatter)
error_logger.addHandler(error_fh)
error_logger.setLevel(logging.ERROR)

@celery.task
def xc_new_message_handler(request_obj):

    message_obj = xc_extract_event_message_details(request_obj)
    # {"contact_details": contact_obj, "message_type": msg_type, "msg_is_media": msg_is_media, "message_data": message}
    if message_obj["msg_is_media"]:

        ch_tasks_for_receive_and_send_media_msgs = chain(xc_get_attachment_details.s(message_obj),
                                                         xc_download_attachment.s(),
                                                         wa_services.wa_upload_media_handler.s(),
                                                         wa_services.wa_send_message_to_whatsapp_user.s())

        ch_tasks_for_receive_and_send_media_msgs_obj = ch_tasks_for_receive_and_send_media_msgs.delay()

        try:
            return ch_tasks_for_receive_and_send_media_msgs_obj
        except Exception as exc:
            error_logger.error(f"Error while handling new message from XCally,\n Error details : {exc}")
            # Retry the chain of chain_tasks_for_received_msgs
            pass

    else: # if not media
        ch_tasks_for_send_txt_msgs = chain(wa_services.wa_send_message_to_whatsapp_user.s({"msg_obj":message_obj}))
        ch_tasks_for_send_txt_msgs_obj = ch_tasks_for_send_txt_msgs.delay()
        try:
            return ch_tasks_for_send_txt_msgs_obj
        except Exception as exc:
            error_logger.error(f"Error while handling new message from XCally,\n Error details : {exc}")
            # Retry the chain of chain_tasks_for_received_msgs
            pass


def xc_extract_event_message_details(message:dict[str,Any]):

    contact_obj= message["contact"] # the customer details
    msg_type = "text"
    msg_is_media = False

    if "AttachmentId" in message.keys():

        # msg_type_cat = xc_get_attachment_type_extension(message["AttachmentId"])
        # msg_type = msg_type_cat["mime_type_category"]
        msg_is_media = True

    return {"contact_details": contact_obj, "message_type": msg_type, "msg_is_media": msg_is_media,
            "message_data": message}


# 1) Get Attachment Details
@celery.task(bind=True, max_retries=max_retries_for_tasks, default_retry_delay=tasks_retry_delay)
def xc_get_attachment_details(self,data) -> dict[str,Any]:
    """
    :param self: The task instance
    :param data: An object with the following keys {"contact_details": contact_obj, "message_type": msg_type, "msg_is_media": msg_is_media,"message_data": message}
    :return: {"status","media_data","msg_obj"}
    """
    # TODO :Document the response result of getting attachment details
    """
    media_data :{
    
    }
    """

    attachment_id = data["message_data"]["AttachmentId"]
    attachment_url = f"{xcally_base_url}/attachments/{attachment_id}?apikey={xcally_api_key}"

    try:
        response = client.get(url=attachment_url)
        response.raise_for_status()
        return {"status":response.status_code,"media_data":response.json(),"msg_obj":data}

    except httpx.HTTPError as exc:
        error_logger.error(f"Error while getting attachment details from XCally,\n >>> Error details : {exc}")
        handle_task_exceptions(self, "HTTP errors: \n" + exc.__str__())

    except Exception as exc:
        error_logger.error(f"Error while getting attachment details from XCally,\n >>> Error details : {exc}")
        handle_task_exceptions(self, "Caught unexpected exception: \n" + exc.__str__())


# 2) Get Attachment Ttype Extension
def xc_get_attachment_type_extension(attachment_details):

    # TODO : Document the attachment_details keys

    """
    :param attachment_details: ??????
    :return: {"file_extension": file_extension, "mime_type_category": mime_type_category}
    """
    file_extension = None
    attachment_details = attachment_details
    mime_type = attachment_details["type"]
    mime_type_category = mime_type[:mime_type.find("/")]
    the_media_type = mime_type[mime_type.find("/") + 1:] # if image/jpeg , this will take jpeg only

    if mime_type_category == "image" or mime_type_category == "audio" or mime_type_category == "video" :
        file_extension = the_media_type

    if mime_type_category == "application":  # document
        the_media_type = mime_type[mime_type.find("/") + 1:]  # if application/pdf , this will take mp4 only

        """
        For MIME types refer to this link : 
        https://stackoverflow.com/questions/4212861/what-is-a-correct-mime-type-for-docx-pptx-etc
        """

        match the_media_type:
            case "pdf":
                file_extension = "pdf"
            case "vnd.ms-powerpoint":
                file_extension = "ppt"
            case "msword":
                file_extension = "doc"
            case "vnd.ms-excel":
                file_extension = "xls"
            case "vnd.openxmlformats-officedocument.wordprocessingml.document":
                file_extension = "docx"
            case "vnd.openxmlformats-officedocument.presentationml.presentation":
                file_extension = "pptx"
            case "vnd.openxmlformats-officedocument.spreadsheetml.sheet":
                file_extension = "xlsx"

    return {"file_extension": file_extension, "mime_type_category": mime_type_category}


# 3) Download the Attachment
@celery.task(bind=True, max_retries=max_retries_for_tasks, default_retry_delay=tasks_retry_delay)
def xc_download_attachment(self, data):
    """
    :param self: Task instance
    :param data: An object of {"status":response.status_code,"media_data":response.json(),"msg_obj":data}
    :return: {"full_media_path": full_media_path, "msg_obj":data["msg_obj"]}
    """
    #
    attachment_id = data["msg_obj"]["message_data"]["AttachmentId"]
    download_url = f"{xcally_base_url}/attachments/{attachment_id}/download/?apikey={xcally_api_key}"
    attachment_details = data["media_data"]
    file_obj = xc_get_attachment_type_extension(attachment_details)
    msg_type = file_obj["mime_type_category"]
    data["msg_obj"]["message_type"] = msg_type

    try:
        response = client.get(url=download_url)
        response.raise_for_status()
        media_in_binary = response.read()
        media_extension = file_obj["file_extension"]
        media_category = file_obj["mime_type_category"]
        local_folder_path = xcally_local_files_repo
        full_media_path_without_file = r"{0}\{1}".format(local_folder_path, media_category)

        if not os.path.exists(full_media_path_without_file):
            os.makedirs(full_media_path_without_file)

        full_media_path = r"{0}\{1}\{2}.{3}".format(local_folder_path, media_category, attachment_id, media_extension)

        with open(full_media_path, 'wb+') as file_handler:
            file_handler.write(media_in_binary)

        return {"full_media_path": full_media_path, "msg_obj":data["msg_obj"]}

    except httpx.HTTPError as exc:
        error_logger.error(f"Error while downloading the attachment from XCally,\n >>> Error details : {exc}")
        handle_task_exceptions(self, "HTTP errors: \n" + exc.__str__())

    except Exception as exc:
        error_logger.error(f"Error while downloading the attachment from XCally,\n >>> Error details : {exc}")
        handle_task_exceptions(self, "Caught unexpected exception: \n" + exc.__str__())


# 4) Write & Read File Data
@celery.task(bind=True, max_retries=max_retries_for_tasks, default_retry_delay=tasks_retry_delay)
def xc_write_read_file_data(self,downloaded_media_details):

    try:
        with open(downloaded_media_details.get("full_media_path"), 'wb+') as file_handler:
            file_handler.write(downloaded_media_details.get("media_in_binary"))
        return file_handler

    except Exception as exc:
        handle_task_exceptions(self, "Caught unexpected exception: \n" + exc.__str__())


# 5) Send the message to whatsapp user

@celery.task(bind=True, max_retries=max_retries_for_tasks, default_retry_delay=tasks_retry_delay)
def send_message_to_xcally_channel(self,data):
    """

    :param self:
    :param data: {status, "media_data","msg_obj"}  or {"msg_obj"}
    :return:
    """
    global response
    from_user_num = data["msg_obj"]["contact_details"]["wa_id"]
    from_user_name = data["msg_obj"]["contact_details"]["profile"]["name"]

    request_data = {
        "phone": from_user_num,  # Sender Phone Number
        "from": from_user_name,  # Sender Name
        "mapKey": "firstName"
    }

    try:
        if "media_data" in data.keys():  # if media_data is not Null then this message is attachment message
            # 2 Send the message
            attachment_id = data["media_data"]["id"]
            request_data.update({"body": ".", "AttachmentId": attachment_id})  # body is mandatory and not empty
            response = client.post(url=xcally_create_msg_url, json=request_data)
            response.raise_for_status()
        else:
            text_msg = data["msg_obj"]["message_data"]["body"]
            request_data.update({"body": text_msg})
            response = client.post(url=xcally_create_msg_url, json=request_data)
            response.raise_for_status()

        return {"status": response.status_code, "response": response.json()}

    except httpx.HTTPError as exc:
        error_logger.error(f"Error while sending the to XCally channel,\n >>> Error details : {exc}")
        handle_task_exceptions(self, "HTTP errors: \n" + exc.__str__())

    except Exception as exc:
        error_logger.error(f"Error while sending the to XCally channel,\n >>> Error details : {exc}")
        handle_task_exceptions(self, "Caught unexpected exception: \n" + exc.__str__())


@celery.task(bind=True, max_retries=max_retries_for_tasks, default_retry_delay=tasks_retry_delay)
def xc_upload_attachment(self,data):
    """

    :param self: The task instance
    :param data: {"full_media_path","msg_obj"}
    :return: {status, "media_data","msg_obj"}
    """

    """
    media_data:
    {
        
    }
    """

    upload_url = xcally_base_url+"/attachments?apikey="+xcally_api_key

    file_path = data.get("full_media_path")

    try:
        media_file = open(file_path,"rb")
        attachment_files = {'file': media_file}
        response = client.post(url=upload_url, files=attachment_files)
        response.raise_for_status()
        return {"status": response.status_code, "media_data": response.json(),"msg_obj":data.get("msg_obj")}

    except httpx.HTTPError as exc:
        error_logger.error(f"Error while uploading the attachment files to XCally,\n >>> Error details : {exc}")
        handle_task_exceptions(self, "HTTP errors: \n" + exc.__str__())

    except Exception as exc:
        error_logger.error(f"Error while uploading the attachment files to XCally,\n >>> Error details : {exc}")
        handle_task_exceptions(self, "Caught unexpected exception: \n" + exc.__str__())




def handle_task_exceptions(self, message):
    print(message)
    if self.request.retries < self.max_retries:
        raise self.retry()
    raise Exception(message)


@celery.task
def xc_failed_tasks_handler():
    # Create a session
    try:
        with Session() as session:
            # Fetch data from the 'failed_tasks' table
            failed_tasks = session.query(FailedTask).all()

            print("=" * 50)
            print(failed_tasks)
            print("=" * 50)
            for task in failed_tasks:
                print(task)
                chain_task = generate_chain_task_for_faild_task(task)

                if chain_task is None :
                    continue

                print("=" * 50)
                print("Waiting Results")
                task_obj = chain_task.apply_async(queue="failed_tasks")
                try:
                    if task_obj.get():
                        on_success_for_failed_tasks(task.id)
                    print(task_obj)
                except Exception as exc:
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

    """
    SQLAlchemy will usually create a column of type VARCHAR or TEXT in the underlying database.
    The JSON data you insert into this column will be stored as a string.
    """
    task_args_str = task.args

    # Replace single quotes with double quotes to make it valid JSON
    valid_json_string = task_args_str.replace("'", '"').replace("False", "false").replace("True", "true").replace("None","null")
    json_data = json.loads(valid_json_string)
    task_args_obj = json_data[0]

    if task.task_name.endswith("xc_get_attachment_details"):
        task_sig = chain(xc_get_attachment_details.s(task_args_obj).set(queue='failed_tasks'),
                         xc_download_attachment.s().set(queue='failed_tasks'),
                         wa_services.wa_upload_media_handler.s().set(queue='failed_tasks'),
                         wa_services.wa_send_message_to_whatsapp_user.s().set(queue='failed_tasks'))

    if task.task_name.endswith("xc_download_attachment"):  # the url of the download expired, and you want to start again
        task_sig = chain(xc_download_attachment.s(task_args_obj).set(queue='failed_tasks'),
                         wa_services.wa_upload_media_handler.s().set(queue='failed_tasks'),
                         wa_services.wa_send_message_to_whatsapp_user.s().set(queue='failed_tasks'))

    if task.task_name.endswith("wa_upload_media_handler"):
        task_sig = chain(wa_services.wa_upload_media_handler.s(task_args_obj).set(queue='failed_tasks'),
                         wa_services.wa_send_message_to_whatsapp_user.s().set(queue='failed_tasks'))

    if task.task_name.endswith("wa_send_message_to_whatsapp_user"):
        task_sig = chain(wa_services.wa_send_message_to_whatsapp_user.s(task_args_obj).set(queue='failed_tasks'))

    else :
        return None

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
