from typing import Any
from root.global_vars import *
import httpx
import os
from root.services import xcally_services as xc_services
from root.tasks_config import celery
from celery import chain

# client = httpx.AsyncClient()
client = httpx.Client()

max_retries_for_tasks = 3
tasks_retry_delay = 10


"""
  *********  Process from receiving the message from WA to XCally ( in case the message type is media ) *******

    1) Get Media Details => wa_get_media_details

    2) Get Media Ttype Extension => wa_get_media_type_extension

    3) Download the Media => wa_download_media

    4) Write & Read File Data => wa_write_read_file_data

    5) Send the message to XCally => wa_send_message_to_whatsapp_user
 ==================================================================================================================

  *********  Process from receiving the message from WA to XCally ( in case the message type is text ) *******

    1)  Send the message to XCally => wa_send_message_to_whatsapp_user

 ==================================================================================================================
"""

def new_event_from_wa_handler(wa_msg_data):
    message_send_response = {}

    # check if the event from the user or from the server
    event_type = wa_check_event_type(wa_msg_data)

    if event_type == "server_event":
        # for example 'status' changed to 'delivered' or 'sent' or 'read'
        print("*" * 50)
        print("JUST SERVER MESSAGE")
        print("*" * 50)
        return None

    # 1) Check if the message is media or just a text and return the result as follows :
    # {"sender_details": contact_obj, "message_type":message_type, "msg_is_media":msg_is_media, "message_data":message_data}

    message_obj = wa_extract_messages_details(wa_msg_data)

    if message_obj.get("message_data") is None:
        # for example react on the message or sending stickers
        print("*" * 50)
        print("UNSUPPORTED MESSAGE CONTENT")
        print("*" * 50)
        return None

    # 2) If media:

    if message_obj.get("msg_is_media"):

        media_id = message_obj.get("message_data").get("id")
        # 2.A =>  Download this media, and get the result as follows :

        chain_tasks_for_received_msgs = chain(wa_get_media_details.s(media_id),
                                              wa_download_media.s(),
                                              wa_write_read_file_data.s())

        chain_tasks_for_received_msgs_obj = chain_tasks_for_received_msgs.delay()

        try:
            file = chain_tasks_for_received_msgs_obj.get()
            ch_tasks_for_send_msgs = send_chain_tasks_based_on_msg_type(
                from_user_num=message_obj.get("sender_details")["wa_id"],
                from_user_name=message_obj.get("sender_details")["profile"]["name"],
                file=file
            )

            ch_tasks_for_send_msgs_obj = ch_tasks_for_send_msgs.delay()
            try:
                return ch_tasks_for_send_msgs_obj.get()

            except Exception as exc:
                # Retry the chain of ch_tasks_for_send_msgs
                pass

        except Exception as exc:
            # Retry the chain of chain_tasks_for_received_msgs
            pass


    else:  # Not media message
        # 3) Send the message to the XCally and (check if message sent to return the result)
        ch_tasks_for_send_msgs = send_chain_tasks_based_on_msg_type(
                from_user_num=message_obj.get("sender_details")["wa_id"],
                from_user_name=message_obj.get("sender_details")["profile"]["name"],
                text_msg=message_obj.get("message_data")["body"]
        )
        ch_tasks_for_send_msgs_obj = ch_tasks_for_send_msgs.delay()
        try:
            return ch_tasks_for_send_msgs_obj.get()
        except Exception as exc:
            # Retry the chain of chain_tasks_for_received_msgs
            pass


def wa_extract_messages_details(messages:dict[str,Any]):

    """
    :param messages: The received from whatsapp user
    :return: An object with the following keys [ sender_details ,message_type , msg_is_media , message_data]
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

    return {"sender_details": contact_obj, "message_type":message_type, "msg_is_media":msg_is_media, "message_data":message_data}


@celery.task(bind=True, max_retries=max_retries_for_tasks, default_retry_delay=tasks_retry_delay)
def wa_get_media_details(self,media_id):

    header_auth = {"Authorization": "Bearer " + access_token}
    try:
        response = client.get(url="https://graph.facebook.com/v19.0/"+media_id, headers=header_auth)
        response.raise_for_status()
        return {"status": response.status_code, "data": response.json()}

    except httpx.HTTPError as exc:
        handle_task_exceptions(self, "HTTP errors: \n" + exc.__str__())

    except Exception as exc:
        handle_task_exceptions(self, "Caught unexpected exception: \n" + exc.__str__())


def wa_get_media_type_extension(media_details):

    """
    :param media_details: the url,mime_type,sha256,file_size,id
    :param self: the task instance
    :return: object contains file_extension and mime_type_category
    """
    media_data = media_details["data"]
    mime_type = media_data["mime_type"]
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
def wa_download_media(self,media_data):

    """
    :param media_details: dict of {"file_extension","mime_type_category","media_data"}
    :param self: the task instance
    :return: the download status along with the local path in case was successfully downloaded

    **Note**:media_data key is a dict with the following details {"url","mime_type","sha256","file_size","id"}
    """
    # Supported Media Types => audio, document, image, video
    media_url = media_data["data"]["url"]
    media_id = media_data["data"]["id"]
    media_type_extension = wa_get_media_type_extension(media_data)
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

        if not os.path.exists(local_folder_path):
            os.makedirs(local_folder_path)

        full_media_path = r"{0}\{1}\{2}.{3}".format(local_folder_path,media_category,media_id,media_extension)

        return {"media_in_binary": media_in_binary, "full_media_path": full_media_path}

    except httpx.HTTPError as exc:
        handle_task_exceptions(self, "HTTP errors: \n" + exc.__str__())

    except Exception as exc:
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
def wa_upload_media_handler(self,filename,file,media_type:str):
    """
    :param file: the media file (image , docs, voice , audio , etc...)
    :param media_type: the type of media, for example : image
    :return: { "id": < The media id stored in meta > }
    """

    media_file = {"file": (filename,file)}
    form_data = {"type": media_type, "messaging_product": "whatsapp"}
    header_auth = {"Authorization":"Bearer "+access_token}

    try:
        response = client.post(url=wa_media_url, data=form_data, files=media_file, headers=header_auth)
        response.raise_for_status()
        return {"status": response.status_code, "data": response.json()}

    except httpx.HTTPError as exc:
        handle_task_exceptions(self, "HTTP errors: \n" + exc.__str__())

    except Exception as exc:
        handle_task_exceptions(self, "Caught unexpected exception: \n" + exc.__str__())


@celery.task(bind=True, max_retries=max_retries_for_tasks, default_retry_delay=tasks_retry_delay)
def wa_send_message_to_whatsapp_user(self,media_data,customer_phone_num,msg_type,message_content):

    header_auth = {"Authorization": "Bearer " + access_token}
    response = {}
    request_data = {}

    try:
        if media_data:
            media_id = media_data["data"]["id"]
            request_data = {"messaging_product": "whatsapp","to":customer_phone_num,"type": msg_type, msg_type:{"id":media_id}}
            response = client.post(url=wa_request_url, json=request_data, headers=header_auth)
        else:
            json_data = {"messaging_product": "whatsapp","to":customer_phone_num,'type': msg_type,"text":{"preview_url":True,"body":message_content}}
            response = client.post(url=wa_request_url, json=json_data, headers=header_auth)
        return {"status": response.status_code, "data": response.json()}

    except httpx.HTTPError as exc:
        handle_task_exceptions(self, "HTTP errors: \n" + exc.__str__())

    except Exception as exc:
        handle_task_exceptions(self, "Caught unexpected exception: \n" + exc.__str__())



def wa_check_event_type(event_obj:dict[str,Any]):
    val_obj = dict()
    val_obj = event_obj["entry"][0]["changes"][0]["value"]

    if "messages" in val_obj.keys():
        return "user_event"
    return "server_event"

def handle_task_exceptions(self, message):
    print(message)
    if self.request.retries < self.max_retries:
        raise self.retry()
    raise Exception("XCally Task, Max Retries Reached!!, going to retry the chain in failed Queue")

def send_chain_tasks_based_on_msg_type(from_user_num, from_user_name, text_msg=None, file=None):
    if file:
        chain_tasks_for_send_msgs = chain(
            xc_services.xc_upload_attachment.s(media_file = file),
            xc_services.send_message_to_xcally_channel.s(
                from_user_num=from_user_num,
                from_user_name=from_user_name,
                text_msg=None
            )
        )

        return chain_tasks_for_send_msgs
    else:
        chain_tasks_for_send_msgs = chain(
            xc_services.send_message_to_xcally_channel.s(
                attachment_Id = None,
                from_user_num=from_user_num,
                from_user_name=from_user_name,
                text_msg = text_msg
            )
        )

        return chain_tasks_for_send_msgs