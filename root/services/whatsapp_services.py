import json
from typing import Any
from root.config_vars import *
import httpx
from root.services import xcally_services as xc_services
from root.celery import celery
from celery import chain
import os
import logging
from root.automation.failed_task_trigger import *

client = httpx.Client()

max_retries_for_tasks = 3
tasks_retry_delay = 10


"""
  *********  Process from receiving the message from WA to XCally ( in case the message type is media ) *******

    1) Get Media Details => wa_get_media_details

    2) Get Media Ttype Extension => wa_get_media_type_extension

    3) Download the Media => wa_download_media
    
    4) Upload the Media => xc_upload_attachment
    
    5) Send the message to XCally => send_message_to_xcally_channel
 ==================================================================================================================

  *********  Process from receiving the message from WA to XCally ( in case the message type is text ) *******

    1)  Send the message to XCally => send_message_to_xcally_channel

 ==================================================================================================================
"""

if not os.path.exists(meta_xcally_logs_dir_path):
    os.makedirs(meta_xcally_logs_dir_path)

formatter = logging.Formatter('[ %(asctime)s ] - Code Line : [ %(lineno)d ] - %(name)s - %(levelname)s - %(message)s')

error_logger = logging.getLogger(__name__)
error_fh = logging.FileHandler(wa_logs_path)
error_fh.setFormatter(formatter)
error_logger.addHandler(error_fh)
error_logger.setLevel(logging.ERROR)


@celery.task
def wa_new_message_handler(wa_msg_data):
    """
    :param wa_msg_data: The message object
    :return:
    """
    message_obj = wa_extract_messages_details(wa_msg_data)
    # message_obj = {"contact_details", "message_type", "msg_is_media", "message_data"}

    if message_obj.get("msg_is_media"):

        ch_tasks_for_receive_and_send_media_msgs = chain(wa_get_media_details.s(message_obj),
                                              wa_download_media.s(),
                                              xc_services.xc_upload_attachment.s(),
                                              xc_services.send_message_to_xcally_channel.s()
                                              )

        ch_tasks_for_receive_and_send_media_msgs_obj = ch_tasks_for_receive_and_send_media_msgs.delay()

        try:
            return ch_tasks_for_receive_and_send_media_msgs_obj

        except Exception as exc:
            error_logger.error(f"Error while handling the new message from WhatsApp,\n >>> Error details : {exc}")
            # Retry the chain of chain_tasks_for_received_msgs
            pass


    else:  # Not media message
        # 3) Send the message to the XCally and (check if message sent to return the result)
        ch_tasks_for_send_txt_msgs = chain(xc_services.send_message_to_xcally_channel.s({"msg_obj":message_obj}))
        ch_tasks_for_send_txt_msgs_obj = ch_tasks_for_send_txt_msgs.delay()
        try:
            return ch_tasks_for_send_txt_msgs_obj
        except Exception as exc:
            error_logger.error(f"Error while handling the new message from WhatsApp,\n >>> Error details : {exc}")
            # Retry the chain of chain_tasks_for_received_msgs
            pass

def wa_extract_messages_details(messages:dict[str,Any]):

    """
    :param messages: The received from whatsapp user
    :return: An object with the following keys { contact_details ,message_type , msg_is_media , message_data }
    """

    # val_obj = entry -> [0] -> changes -> [0] -> value
    # contact_obj =  val_obj -> contacts -> [0]
    # contact_name = contact_obj -> profile -> name
    # contact_wa_id = contact_obj -> wa_id
    # message_obj = val_obj -> messages -> [0]
    # message_type = message_obj -> type

    val_obj = messages["entry"][0]["changes"][0]["value"]
    contact_obj = val_obj["contacts"][0]
    message_obj = val_obj["messages"][0]
    message_type = message_obj["type"]
    message_data = {}
    msg_is_media = False

    if message_type == "text":
        message_data = message_obj["text"]

    elif message_type == "image":
        message_data = message_obj["image"]
        msg_is_media = True

    elif message_type == "document":
        message_data = message_obj["document"]
        msg_is_media = True

    elif message_type == "audio":
        message_data = message_obj["audio"]
        msg_is_media = True

    elif message_type == "video":
        message_data = message_obj["video"]
        msg_is_media = True

    else: # unsupported message content
        message_data = None

    return {"contact_details": contact_obj, "message_type":message_type, "msg_is_media":msg_is_media, "message_data":message_data}


@celery.task(bind=True, max_retries=max_retries_for_tasks, default_retry_delay=tasks_retry_delay)
def wa_get_media_details(self,data):
    """
    :param self: Task instance
    :param data: An object with the following keys { contact_details ,message_type , msg_is_media , message_data }
    :return: Object with the following keys {"status", "media_data","msg_obj"}
    """

    """
    media_data:{
      "messaging_product": "whatsapp",
      "url": "<URL>",
      "mime_type": "<MIME_TYPE>",
      "sha256": "<HASH>",
      "file_size": "<FILE_SIZE>",
      "id": "<MEDIA_ID>"
    }
    """

    media_id = data.get("message_data").get("id")
    msg_obj = data

    header_auth = {"Authorization": "Bearer " + access_token}
    try:
        response = client.get(url="https://graph.facebook.com/v19.0/"+media_id, headers=header_auth)
        response.raise_for_status()
        return {"status": response.status_code, "media_data": response.json(),"msg_obj":msg_obj}

    except httpx.HTTPError as exc:
        error_logger.error(f"Error while getting the media details from WhatsApp,\n >>> Error details : {exc}")
        handle_task_exceptions(self, "HTTP errors: \n" + exc.__str__())

    except Exception as exc:
        error_logger.error(f"Error while getting the media details from WhatsApp,\n >>> Error details : {exc}")
        handle_task_exceptions(self, "Caught unexpected exception: \n" + exc.__str__())


def wa_get_media_type_extension(mime_type):

    """
    :param mime_type: for example : image/jpeg
    :return: object contains file_extension and mime_type_category
    """
    file_extension = ""
    mime_type_category = mime_type[:mime_type.find("/")]
    the_media_type = mime_type[mime_type.find("/") + 1:]  # for example : if image/jpeg , this will take jpeg only

    if mime_type_category == "image" or mime_type_category == "audio" or mime_type_category == "video" :
        file_extension = the_media_type

    if mime_type_category == "text": # plain text document
        file_extension = "txt"

    if mime_type_category == "application": # document
        """
        For MIME types refer to this link : 
        https://stackoverflow.com/questions/4212861/what-is-a-correct-mime-type-for-docx-pptx-etc
        """

        match the_media_type:
            case "pdf": file_extension = "pdf"
            case "vnd.ms-powerpoint": file_extension = "ppt"
            case "msword": file_extension = "doc"
            case "vnd.ms-excel": file_extension = "xls"
            case "vnd.openxmlformats-officedocument.wordprocessingml.document": file_extension = "docx"
            case "vnd.openxmlformats-officedocument.presentationml.presentation": file_extension = "pptx"
            case "vnd.openxmlformats-officedocument.spreadsheetml.sheet": file_extension = "xlsx"

    return {"file_extension":file_extension,"mime_type_category":mime_type_category}


@celery.task(bind=True, max_retries=max_retries_for_tasks, default_retry_delay=tasks_retry_delay)
def wa_download_media(self,data):

    """
    :param data: dict of {"status","media_data","msg_obj"}
    :param self: the task instance
    :return: {"full_media_path": full_media_path,"msg_obj":data.get("msg_obj")}

    **Note**:data key is a dict with the following details {"url","mime_type","sha256","file_size","id"}
    """

    # Supported Media Types => audio, document, image, video
    media_url = data["media_data"]["url"]
    media_id = data["media_data"]["id"]
    media_type_extension = wa_get_media_type_extension(data["media_data"]["mime_type"])
    header_auth = {"Authorization": "Bearer " + access_token}

    try:
        response = client.get(url=media_url, headers=header_auth)
        response.raise_for_status()  # in case there is an error while calling the API
        # check if the media url is valid,
        # All media URLs expire after 5 minutes — you need to retrieve the media URL again if it expires
        media_in_binary = response.read()
        media_extension = media_type_extension["file_extension"]
        media_category = media_type_extension["mime_type_category"]
        local_folder_path = wa_local_files_repo
        full_media_path_without_file = r"{0}\{1}".format(local_folder_path, media_category)

        if not os.path.exists(full_media_path_without_file):
            os.makedirs(full_media_path_without_file)

        full_media_path = r"{0}\{1}\{2}.{3}".format(local_folder_path,media_category,media_id,media_extension)

        with open(full_media_path, 'wb') as file_handler:
            file_handler.write(media_in_binary)

        return {"full_media_path": full_media_path,"msg_obj":data.get("msg_obj")}

    except httpx.HTTPError as exc:
        error_logger.error(f"Error while downloading the media from WhatsApp,\n >>> Error details : {exc}")
        handle_task_exceptions(self, "HTTP errors: \n" + exc.__str__())

    except Exception as exc:
        error_logger.error(f"Error while downloading the media from WhatsApp,\n >>> Error details : {exc}")
        handle_task_exceptions(self, "Caught unexpected exception: \n" + exc.__str__())


@celery.task(bind=True, max_retries=max_retries_for_tasks, default_retry_delay=tasks_retry_delay)
def wa_write_read_file_data(self,downloaded_media_details):

    try:
        with open(downloaded_media_details.get("full_media_path"), 'wb+') as file_handler:
            file_handler.write(downloaded_media_details.get("media_in_binary"))
        return file_handler

    except Exception as exc:
        handle_task_exceptions(self, "Caught unexpected exception: \n" + exc.__str__())


@celery.task(bind=True, max_retries=max_retries_for_tasks, default_retry_delay=tasks_retry_delay)
def wa_upload_media_handler(self,data):

    """
    :param data: {"full_media_path", "msg_obj"}
    :return: {"status", "media_data","msg_obj"}
    """

    filename = data["msg_obj"]["message_data"]["body"]
    media_type = data["msg_obj"]["message_type"]

    form_data = {"type": media_type, "messaging_product": "whatsapp"}
    header_auth = {"Authorization":"Bearer "+access_token}

    try:
        file = open(data["full_media_path"], "rb")
        media_file = {"file": (filename, file)}
        response = client.post(url=wa_media_url, data=form_data, files=media_file, headers=header_auth)
        response.raise_for_status()
        return {"status": response.status_code, "media_data": response.json(),"msg_obj":data["msg_obj"]}

    except httpx.HTTPError as exc:
        error_logger.error(f"Error while uploading the media to WhatsApp,\n >>> Error details : {exc}")
        handle_task_exceptions(self, "HTTP errors: \n" + exc.__str__())

    except Exception as exc:
        error_logger.error(f"Error while uploading the media to WhatsApp,\n >>> Error details : {exc}")
        handle_task_exceptions(self, "Caught unexpected exception: \n" + exc.__str__())


@celery.task(bind=True, max_retries=max_retries_for_tasks, default_retry_delay=tasks_retry_delay)
def wa_send_message_to_whatsapp_user(self,data):

    """
    :param self: task instance
    :param data: {"status", "media_data","msg_obj"}
    :return:{"status": response.status_code, "response": response.json()}
    """

    customer_phone_num = data["msg_obj"]["contact_details"]["phone"]
    msg_type = data["msg_obj"]["message_type"]
    header_auth = {"Authorization": "Bearer " + access_token}
    global response
    global request_data

    try:
        if "media_data" in data.keys():
            media_id = data["media_data"]["id"]
            request_data = {"messaging_product": "whatsapp","to":customer_phone_num,"type": msg_type, msg_type:{"id":media_id}}
            error_logger.error("---------------------------------------------")
            error_logger.error(request_data)
            error_logger.error("---------------------------------------------")
            response = client.post(url=wa_request_url, json=request_data, headers=header_auth)
            response.raise_for_status()
        else:
            message_content = data["msg_obj"]["message_data"]["body"]
            json_data = {"messaging_product": "whatsapp","to":customer_phone_num,'type': msg_type,"text":{"preview_url":True,"body":message_content}}
            response = client.post(url=wa_request_url, json=json_data, headers=header_auth)
            response.raise_for_status()
        return {"status": response.status_code, "response": response.json()}

    except httpx.HTTPError as exc:
        error_logger.error(f"Error while sending the message to WhatsApp,\n >>> Error details : {exc}")
        handle_task_exceptions(self, "HTTP errors: \n" + exc.__str__())

    except Exception as exc:
        error_logger.error(f"Error while sending the message to WhatsApp,\n >>> Error details : {exc}")
        handle_task_exceptions(self, "Caught unexpected exception: \n" + exc.__str__())



def wa_check_event_type(event_obj:dict[str,Any]):
    val_obj = dict()
    val_obj = event_obj["entry"][0]["changes"][0]["value"]

    if "messages" in val_obj.keys():
        return "user_event"
    return "server_event"

def wa_msg_is_valid(event_obj:dict[str,Any]):
    val_obj = event_obj["entry"][0]["changes"][0]["value"]
    message_obj = val_obj["messages"][0]
    message_type = message_obj["type"]
    global msg_is_valid

    if message_type == "text" or message_type == "image" or message_type == "document" or message_type == "audio" or message_type == "video":
        msg_is_valid = True
    else:  # unsupported message content
        msg_is_valid = False

    return msg_is_valid

def handle_task_exceptions(self, message):
    print(message)
    if self.request.retries < self.max_retries:
        raise self.retry()
    raise Exception(message)




