from typing import Annotated, Any
from root.tasks_config import celery
from celery import chain
from root.global_vars import *
import httpx
import os
from root.services import whatsapp_services as wa_services

client = httpx.Client(verify=False)

max_retries_for_tasks = 3
tasks_retry_delay = 10

"""
  *********  Process from receiving the message from XCally to WA ( in case the message type is media ) *******

    1) Get Attachment Details => xc_get_attachment_details

    2) Get Attachment Ttype Extension => xc_get_attachment_type_extension

    3) Download the Attachment => xc_download_attachment

    4) Write & Read File Data => xc_write_read_file_data

    5) Send the message to WA => send_message_to_xcally_channel
 ==================================================================================================================

  *********  Process from receiving the message from XCally to WA ( in case the message type is text ) *******

    1)  Send the message to WA => send_message_to_xcally_channel

 ==================================================================================================================
"""


def new_event_from_xcally_handler(request_obj):
    message_obj = xc_extract_event_message_details(request_obj)
    send_msg_to_wa_customer_response = {}
    customer_details = message_obj["customer_details"]
    message_type = message_obj["message_type"]

    if message_obj["msg_is_media"]:
        # Download the attachment first
        attachment_id = message_obj["message_data"]["AttachmentId"]
        # this chain should return file to be uploaded
        chain_tasks_for_received_msgs = chain(xc_get_attachment_details.s(attachment_id),
                                              xc_download_attachment.s(attachment_id=attachment_id),
                                              xc_write_read_file_data.s())

        ch_tasks_for_received_msgs_obj = chain_tasks_for_received_msgs.delay()

        try:
            file = ch_tasks_for_received_msgs_obj.get()
            ## Send the message to the customer ( Meta API )
            ch_tasks_for_send_msgs = send_chain_tasks_based_on_msg_type(message_body=message_obj["message_data"]["body"],
                                                                        file=file,
                                                                        msg_type=message_type,
                                                                        customer_phone_num=customer_details["phone"])
            ch_tasks_for_send_msgs_obj = ch_tasks_for_send_msgs.delay()
            try:
                return ch_tasks_for_send_msgs_obj.get()

            except Exception as exc:
                # Retry the chain of ch_tasks_for_send_msgs
                pass

        except Exception as exc:
            # Retry the chain of chain_tasks_for_received_msgs
            pass

    else: # if not media
        ch_tasks_for_send_msgs = send_chain_tasks_based_on_msg_type(customer_phone_num=customer_details["phone"],
                                                                    msg_type=message_type,
                                                                    message_body=message_obj["message_data"]["body"])
        ch_tasks_for_send_msgs_obj = ch_tasks_for_send_msgs.delay()
        try:
            return ch_tasks_for_send_msgs_obj.get()
        except Exception as exc:
            # Retry the chain of chain_tasks_for_received_msgs
            pass


# 1) Get Attachment Details
@celery.task(bind=True, max_retries=max_retries_for_tasks, default_retry_delay=tasks_retry_delay)
def xc_get_attachment_details(self,attachment_id) -> dict[str,Any]:

    attachment_url = f"{xcally_base_url}/attachments/{attachment_id}?apikey={xcally_api_key}"

    try:
        response = client.get(url=attachment_url)
        response.raise_for_status()
        return {"status":response.status_code,"data":response.json()}

    except httpx.HTTPError as exc:
        handle_task_exceptions(self, "HTTP errors: \n" + exc.__str__())

    except Exception as exc:
        handle_task_exceptions(self, "Caught unexpected exception: \n" + exc.__str__())


# 2) Get Attachment Ttype Extension
def xc_get_attachment_type_extension(attachment_details):

    file_extension = None
    media_obj = attachment_details

    media_data = media_obj["data"]
    mime_type = media_data["type"]
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
def xc_download_attachment(self, attachment_details, attachment_id):
    download_url = f"{xcally_base_url}/attachments/{attachment_id}/download/?apikey={xcally_api_key}"

    file_obj = xc_get_attachment_type_extension(attachment_details)

    try:
        response = client.get(url=download_url)
        response.raise_for_status()
        media_in_binary = response.read()
        media_extension = file_obj["file_extension"]
        media_category = file_obj["mime_type_category"]
        local_folder_path = xcally_local_files_repo
        full_media_path_without_file = r"{0}\{1}".format(local_folder_path, media_category, attachment_id,
                                                         media_extension)

        if not os.path.exists(full_media_path_without_file):
            os.makedirs(full_media_path_without_file)

        full_media_path = r"{0}\{1}\{2}.{3}".format(local_folder_path, media_category, attachment_id, media_extension)

        return {"media_in_binary": media_in_binary, "full_media_path": full_media_path}

    except httpx.HTTPError as exc:
        handle_task_exceptions(self, "HTTP errors: \n" + exc.__str__())

    except Exception as exc:
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
def send_message_to_xcally_channel(self,from_user_num,from_user_name,text_msg:str = None, attachment_Id = None ):
    response = {}
    request_data = {
        "phone": from_user_num,  # Sender Phone Number
        "from": from_user_name,  # Sender Name
        "mapKey": "firstName"
    }

    try:
        if attachment_Id:  # if attachment_Id is not Null then this message is attachment message
            # 2 Send the message
            request_data.update({"body": ".", "AttachmentId": attachment_Id})  # body is mandatory and not empty
            response = client.post(url=xcally_create_msg_url, json=request_data)
        else:
            request_data.update({"body": text_msg})
            response = client.post(url=xcally_create_msg_url, json=request_data)

        return {"status": response.status_code, "data": response.json()}

    except httpx.HTTPError as exc:
        handle_task_exceptions(self, "HTTP errors: \n" + exc.__str__())

    except Exception as exc:
        handle_task_exceptions(self, "Caught unexpected exception: \n" + exc.__str__())


@celery.task(bind=True, max_retries=max_retries_for_tasks, default_retry_delay=tasks_retry_delay)
def xc_upload_attachment(self,media_file):
    upload_url = xcally_base_url+"/attachments?apikey="+xcally_api_key
    attachment_files = {'file': media_file}

    try:
        response = client.post(url=upload_url, files=attachment_files)
        return {"status": response.status_code, "data": response.json()}

    except httpx.HTTPError as exc:
        handle_task_exceptions(self, "HTTP errors: \n" + exc.__str__())

    except Exception as exc:
        handle_task_exceptions(self, "Caught unexpected exception: \n" + exc.__str__())


def xc_extract_event_message_details(message:dict[str,Any]):

    contact_details = message["contact"] # the customer details
    msg_type = "text"
    msg_is_media = False

    if "AttachmentId" in message.keys():

        msg_type_cat = xc_get_attachment_type_extension(message["AttachmentId"])
        msg_type = msg_type_cat["mime_type_category"]
        msg_is_media = True

    return {"customer_details": contact_details, "message_type": msg_type, "msg_is_media": msg_is_media,
            "message_data": message}


def handle_task_exceptions(self, message):
    print(message)
    if self.request.retries < self.max_retries:
        raise self.retry()
    raise Exception("XCally Task, Max Retries Reached!!, going to retry the chain in failed Queue")

def send_chain_tasks_based_on_msg_type(customer_phone_num, msg_type, message_body, file=None):
    if file:
        chain_tasks_for_send_msgs = chain(
            wa_services.wa_upload_media_handler.s(
                filename=message_body,
                media_type=msg_type,
                file = file),
            wa_services.wa_send_message_to_whatsapp_user.s(
                customer_phone_num=customer_phone_num,
                msg_type=msg_type,
                message_content=None
            )
        )

        return chain_tasks_for_send_msgs
    else:
        chain_tasks_for_send_msgs = chain(
            wa_services.wa_send_message_to_whatsapp_user.s(
                media_data = None,
                customer_phone_num=customer_phone_num,
                msg_type = msg_type,
                message_content = message_body
            )
        )

        return chain_tasks_for_send_msgs
