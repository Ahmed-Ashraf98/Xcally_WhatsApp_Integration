from typing import Annotated, Any
from fastapi.responses import PlainTextResponse
import httpx

client = httpx.AsyncClient()

wa_verify_token = "Sana"
phone_number_id = "209325405605976"
access_token = "EAARxAciB8DkBO89zuix7B5WE9ZBUdhyZASkavn9XueUM6ajocrQ3DYNSlG3OmoKxKc2pGV8CbZBtZCMa54ihtsDyTDz2FZAdcwJKaMVcb1iMhq3yU1kQIqZCvKzvRGYV6dwXQHB6qoWwE41Gi3BxRZCnidoaDbPGsZA4YNRh0NiM0VZBC1sQVrGEd1HsplajAJ40gsWvh1hwFopV0rfKDxXbj00fmQhQZD"
wa_request_url = "https://graph.facebook.com/v19.0/"+phone_number_id+"/messages"
wa_media_url = "https://graph.facebook.com/v19.0/"+phone_number_id+"/media"

def wa_get_media_type_extension(mime_type:str):

    """
    :param mime_type: the MIME type as string, for example image/jpeg
    :return: object contains file_extension and mime_type_category
    """

    file_extension = ""
    mime_type_category = mime_type[:mime_type.find("/")]

    if mime_type_category == "image":
        the_media_type = mime_type[mime_type.find("/")+1:] # if image/jpeg , this will take jpeg only
        file_extension = the_media_type

    if mime_type_category == "audio":
        the_media_type = mime_type[mime_type.find("/") + 1:]  # if audio/mp4 , this will take mp4 only
        file_extension = the_media_type

    if mime_type_category == "video":
        the_media_type = mime_type[mime_type.find("/") + 1:]  # if video/mp4 , this will take mp4 only
        file_extension = the_media_type

    if mime_type_category == "text": # plain text document
        file_extension = "txt"

    if mime_type_category == "application": # document
        the_media_type = mime_type[mime_type.find("/") + 1:]  # if application/pdf , this will take mp4 only

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


async def wa_get_received_messages_details(messages:dict[str,Any]):

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

    return {"sender_details": contact_obj, "message_type":message_type, "msg_is_media":msg_is_media, "message_data":message_data}


async def wa_send_message_to_xcally(sender_obj,msg_type=None,message_content:dict = None, media_file = None):

    header_auth = {"Authorization": "Bearer " + access_token}
    xcally_agent_num = "201066632344"
    response={}
    if media_file:
        media_file = {'file': media_file}
        # to => the XCally agent

        form_data = {"messaging_product": "whatsapp","to":xcally_agent_num,"type": msg_type, msg_type:{"id":message_content["id"]}}
        # response = await client.post(url=wa_media_url, data=form_data, files=media_file, headers=header_auth)
        response = await client.post(url=wa_request_url, json=form_data, headers=header_auth)
    else:
        json_data = {'messaging_product': 'whatsapp',"to":xcally_agent_num,'type': msg_type,"text":{"preview_url":True,"body":message_content["body"]}}
        response = await client.post(url=wa_request_url, json=json_data, headers=header_auth)

    return response.json()

async def wa_get_media_details(media_id):

    header_auth = {"Authorization": "Bearer " + access_token}
    response = await client.get(url="https://graph.facebook.com/v19.0/"+media_id, headers=header_auth)

    if response.status_code == 400 :
        # media id is not found ["Unsupported get request. Object with ID '784052817101446e' does not exist"]
        # Raise an exception or something else
        return None

    if response.status_code == 200:
        response_in_json = response.json()
        return response_in_json


async def wa_download_media(media_id):

    """
    :param media_id: the media id from Meta
    :return: the download status along with the local path in case was successfully downloaded
    """

    # Supported Media Types => audio, document, image, video, sticker

    media_details_obj=await wa_get_media_details(media_id)
    print(media_details_obj)
    media_url = media_details_obj["url"]
    media_mime_type = media_details_obj["mime_type"]
    media_id = media_details_obj["id"]
    header_auth = {"Authorization": "Bearer " + access_token}
    response = await client.get(url=media_url, headers=header_auth)

    # check if the media url is valid, All media URLs expire after 5 minutes — you need to retrieve the media URL again if it expires

    if response.status_code == 404 :
        # Log that image url is not found or expired , and you are going to get new one
        media_details_obj = await wa_get_media_details(media_id)
        media_url = media_details_obj["url"]
        media_mime_type = media_details_obj["mime_type"]
        media_id = media_details_obj["id"]
        response = await client.get(url=media_url, headers=header_auth)

    media_in_binary = response.read()
    media_extension = wa_get_media_type_extension(media_mime_type)["file_extension"]
    local_folder_path =r"C:\Users\aashraf\Desktop\Test_Folder"
    full_media_path = r"{0}\{1}.{2}".format(local_folder_path,media_id,media_extension)

    try:
        with open(full_media_path, 'wb') as file_handler:
            file_handler.write(media_in_binary)

    except:
        return {"status":"failed","message":"Error while writing the media file"}

    return {"status":"success","media_local_path":full_media_path,"message":"The media has been downloaded successfully"}


async def wa_upload_media_handler(file,media_type:str) -> dict:
    """
    :param file: the media file (image , docs, voice , audio , etc...)
    :param media_type: the type of media, for example : image
    :return: { "id": < The media id stored in meta > }
    """
    # for example :  784052817101446
    media_file = None

    media_file = {'file': (file.filename,file.file)}
    form_data = {'type': media_type, 'messaging_product': 'whatsapp'}
    header_auth = {"Authorization":"Bearer "+access_token}
    response = await client.post(url=wa_media_url, data=form_data, files=media_file, headers=header_auth)
    return response.json()



async def wa_check_event_type(event_obj:dict[str,Any]):
    val_obj = dict()
    val_obj = event_obj["entry"][0]["changes"][0]["value"]

    if "messages" in val_obj.keys():
        return "user_event"
    return "server_event"