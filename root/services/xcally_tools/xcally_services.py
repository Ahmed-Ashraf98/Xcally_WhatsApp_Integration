from typing import Annotated, Any
from fastapi.responses import PlainTextResponse
from fastapi import Response
from root.globals import *
import httpx


client = httpx.AsyncClient(verify=False)


async def xc_get_attachment_details(attachment_id) -> dict[str,Any]:
    upload_url = f"{xcally_base_url} + /attachments/{attachment_id}?apikey= + {xcally_api_key}"
    response = await client.get(url=upload_url)
    result = dict()
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
    return response


async def xc_download_attachment(attachment_id):

    download_url = f"{xcally_base_url}+/attachments/{attachment_id}/download/?apikey={xcally_api_key}"
    file_obj = await xc_get_attachment_type_extension(attachment_id)

    response = await client.get(url=download_url)
    media_in_binary = response.read()

    media_extension = file_obj["file_extension"]
    media_cat = file_obj["mime_type_category"]
    local_folder_path = r"C:\Users\aashraf\Desktop\Test_Folder"
    full_media_path = r"{0}\{1}\{2}.{3}".format(local_folder_path,media_cat, attachment_id, media_extension)

    try:
        with open(full_media_path, 'wb') as file_handler:
            file_handler.write(media_in_binary)

    except:
        return {"status": "failed", "message": "Error while writing the media file"}

    return {"status": "success", "media_local_path": full_media_path,
            "message": "The media has been downloaded successfully"}


async def xc_get_event_messages_details(message:dict[str,Any]):

    contact_details = message["contact"] # the customer details
    contact_phone_num = contact_details["phone"]
    message_data = None
    msg_type = None
    msg_is_media = False

    if "AttachmentId" not in message.keys():
        msg_type = "text"
    else:
        msg_type = "media"
        msg_is_media = True

    return {"customer_details": contact_details, "message_type": msg_type, "msg_is_media": msg_is_media,
            "message_data": message_data}


async def send_message_to_xcally_channel(sender_obj,msg_type=None,message_content:dict = None, file = None):

    response={}
    request_data = {
        "phone": sender_obj["wa_id"], # Sender Phone Number
        "from": sender_obj["profile"]["name"],  # Sender Name
        "mapKey": "firstName"
    }

    if file: # if file is not Null then this message is attachment message

        upload_response = await xc_upload_attachment(file)
        response_attach_json = upload_response.json()

        if upload_response.status_code == 201:

            #2 Send the message
            request_data.update({"body": ".","AttachmentId":response_attach_json["id"]}) # body is mandatory and not empty
            response = await client.post(url=xcally_create_msg_url, json=request_data)
        else:
            print("-" * 30)
            print("===== [ ERROR: Attachment Not Uploaded, Please check the error logs ] ====")
            print(response_attach_json.json())
            print("-" * 30)


    else:

        request_data.update({"body": message_content["body"]})
        response = await client.post(url=xcally_create_msg_url, json=request_data)

    print(response.json())
    return response.json()
