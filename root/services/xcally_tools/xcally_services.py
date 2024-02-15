from typing import Annotated, Any
from fastapi.responses import PlainTextResponse
from fastapi import Response
from root.global_vars import *
import httpx
import os


client = httpx.AsyncClient(verify=False)


async def xc_get_attachment_details(attachment_id) -> dict[str,Any]:
    upload_url = f"{xcally_base_url}/attachments/{attachment_id}?apikey={xcally_api_key}"
    response = await client.get(url=upload_url)
    result = dict[str, Any]
    result = {"status":response.status_code,"data":response.json()}
    return result


async def xc_get_attachment_type_extension(attachment_id):

    file_extension = None
    mime_type_category = None
    media_obj = await xc_get_attachment_details(attachment_id)

    if media_obj["status"] == 200:
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
                case "pdf": file_extension = "pdf"
                case "vnd.ms-powerpoint": file_extension = "ppt"
                case "msword": file_extension = "doc"
                case "vnd.ms-excel":file_extension = "xls"
                case "vnd.openxmlformats-officedocument.wordprocessingml.document": file_extension = "docx"
                case "vnd.openxmlformats-officedocument.presentationml.presentation": file_extension = "pptx"
                case "vnd.openxmlformats-officedocument.spreadsheetml.sheet": file_extension = "xlsx"

    else:
        print("Error while getting the Attachment Details")

    return {"file_extension": file_extension, "mime_type_category": mime_type_category}


async def xc_upload_attachment(media_file):
    upload_url = xcally_base_url+"/attachments?apikey="+xcally_api_key
    attachment_files = {'file': media_file}
    response = await client.post(url=upload_url, files=attachment_files)
    result = dict[str, Any]
    result = {"status": response.status_code, "data": response.json()}
    return result


async def xc_download_attachment(attachment_id):

    download_url = f"{xcally_base_url}/attachments/{attachment_id}/download/?apikey={xcally_api_key}"
    file_obj = await xc_get_attachment_type_extension(attachment_id)

    response = await client.get(url=download_url)
    media_in_binary = response.read()

    media_extension = file_obj["file_extension"]
    media_cat = file_obj["mime_type_category"]
    local_folder_path = xcally_local_files_repo
    full_media_path_without_file = r"{0}\{1}".format(local_folder_path,media_cat, attachment_id, media_extension)

    if not os.path.exists(full_media_path_without_file):
        os.makedirs(full_media_path_without_file)

    full_media_path = r"{0}\{1}\{2}.{3}".format(local_folder_path,media_cat, attachment_id, media_extension)

    try:
        with open(full_media_path, 'wb') as file_handler:
            file_handler.write(media_in_binary)

    except Exception as ex:
        print(ex)
        return {"status": "failed", "message": "Error while writing the media file"}

    return {"status": "success", "media_local_path": full_media_path,
            "message": "The media has been downloaded successfully"}


async def xc_extract_event_message_details(message:dict[str,Any]):


    contact_details = message["contact"] # the customer details
    contact_phone_num = contact_details["phone"]
    msg_type = "text"
    msg_is_media = False

    if "AttachmentId" in message.keys():

        msg_type_cat = await xc_get_attachment_type_extension(message["AttachmentId"])
        msg_type = msg_type_cat["mime_type_category"]
        msg_is_media = True

    return {"customer_details": contact_details, "message_type": msg_type, "msg_is_media": msg_is_media,
            "message_data": message}


async def send_message_to_xcally_channel(from_user_num,from_user_name,text_msg:str = None, attachment_Id = None ):
    response = {}
    request_data = {
        "phone": from_user_num,  # Sender Phone Number
        "from": from_user_name,  # Sender Name
        "mapKey": "firstName"
    }

    if attachment_Id:  # if attachment_Id is not Null then this message is attachment message
        # 2 Send the message
        request_data.update({"body": ".", "AttachmentId": attachment_Id})  # body is mandatory and not empty
        response = await client.post(url=xcally_create_msg_url, json=request_data)
    else:
        request_data.update({"body": text_msg})
        response = await client.post(url=xcally_create_msg_url, json=request_data)

    result = dict[str, Any]
    result = {"status": response.status_code, "data": response.json()}
    return result
