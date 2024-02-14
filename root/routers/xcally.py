from fastapi import APIRouter, FastAPI, Body, Query, Request, Response, status, File, UploadFile, Form, HTTPException
from typing import Annotated, Any
from root.globals import *
from root.services.xcally_tools import xcally_services as xc_services
from root.services.whatsapp_tools import whatsapp_services as wa_services

router = APIRouter(prefix="/xcally_webhook",tags=["xcally"])

@router.post("")
async def xcally_new_message_from_agent(request:Request):

    result_of_request = await request.json()
    message_obj = await xc_services.xc_get_event_messages_details(result_of_request)
    # {"customer_details": contact_details, "message_type": msg_type, "msg_is_media": msg_is_media,"message_data": message_data}

    if message_obj["msg_is_media"]:

        # Download the media first
        attachment_id = message_obj["message_data"]["AttachmentId"]
        media_download_response = await xc_services.xc_download_attachment(attachment_id)

        if media_download_response.get("status") == "success" :
            file = open(media_download_response.get("media_local_path"),"rb")

        # Upload image into the Meta

        # Use the returned Media Id to send the message

        # Send the message to the customer (Meta API)

    else: # if not media
        pass

    print(result_of_request)

