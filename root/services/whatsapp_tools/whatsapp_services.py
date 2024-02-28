from typing import Annotated, Any
from fastapi.responses import PlainTextResponse
from root.global_vars import *
import httpx
import os

client = httpx.AsyncClient()


def wa_get_media_type_extension(mime_type:str):

    """
    :param mime_type: the MIME type as string, for example image/jpeg
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


async def wa_send_message_to_whatsapp_user(customer_phone_num,msg_type=None,message_content:dict = None, media_id = None):

    header_auth = {"Authorization": "Bearer " + access_token}
    response = {}
    request_data = {}

    if media_id:
        request_data = {"messaging_product": "whatsapp","to":customer_phone_num,"type": msg_type, msg_type:{"id":media_id}}
        response = await client.post(url=wa_request_url, json=request_data, headers=header_auth)
    else:
        json_data = {"messaging_product": "whatsapp","to":customer_phone_num,'type': msg_type,"text":{"preview_url":True,"body":message_content}}
        response = await client.post(url=wa_request_url, json=json_data, headers=header_auth)

    result = dict[str, Any]
    result = {"status": response.status_code, "data": response.json()}
    return result


async def wa_get_media_details(media_id):

    header_auth = {"Authorization": "Bearer " + access_token}
    response = await client.get(url="https://graph.facebook.com/v19.0/"+media_id, headers=header_auth)

    if response.status_code == 400 :
        # media id is not found ["Unsupported get request. Object with ID '784052817101446e' does not exist"]
        # Raise an exception or something else
        pass

    result = dict[str, Any]
    result = {"status": response.status_code, "data": response.json()}
    return result


async def wa_download_media(media_id):

    """
    :param media_id: the media id from Meta
    :return: the download status along with the local path in case was successfully downloaded
    """

    # Supported Media Types => audio, document, image, video, sticker

    media_details_response = await wa_get_media_details(media_id)
    media_data = media_details_response["data"]
    media_url = media_data["url"]
    media_mime_type = media_data["mime_type"]
    media_id = media_data["id"]
    header_auth = {"Authorization": "Bearer " + access_token}
    response = await client.get(url=media_url, headers=header_auth)

    # check if the media url is valid, All media URLs expire after 5 minutes — you need to retrieve the media URL again if it expires

    if response.status_code == 404 :
        # Log that image url is not found or expired , and you are going to get new one
        media_details_response = await wa_get_media_details(media_id)
        media_data = media_details_response["data"]
        media_url = media_data["url"]
        media_mime_type = media_data["mime_type"]
        media_id = media_data["id"]
        response = await client.get(url=media_url, headers=header_auth)

    media_in_binary = response.read()
    media_extension = wa_get_media_type_extension(media_mime_type)["file_extension"]
    local_folder_path = wa_local_files_repo

    if not os.path.exists(local_folder_path):
        os.makedirs(local_folder_path)

    full_media_path = r"{0}\{1}.{2}".format(local_folder_path,media_id,media_extension)

    try:
        with open(full_media_path, 'wb') as file_handler:
            file_handler.write(media_in_binary)

    except:
        return {"status":"failed","message":"Error while writing the media file"}

    return {"status":"success","media_local_path":full_media_path,"message":"The media has been downloaded successfully"}


async def wa_upload_media_handler(filename,file,media_type:str):
    """
    :param file: the media file (image , docs, voice , audio , etc...)
    :param media_type: the type of media, for example : image
    :return: { "id": < The media id stored in meta > }
    """

    media_file = {"file": (filename,file)}
    form_data = {"type": media_type, "messaging_product": "whatsapp"}
    header_auth = {"Authorization":"Bearer "+access_token}
    response = await client.post(url=wa_media_url, data=form_data, files=media_file, headers=header_auth)
    result = dict[str, Any]
    result = {"status": response.status_code, "data": response.json()}
    return result


def wa_check_event_type(event_obj:dict[str,Any]):
    val_obj = dict()
    val_obj = event_obj["entry"][0]["changes"][0]["value"]

    if "messages" in val_obj.keys():
        return "user_event"
    return "server_event"
