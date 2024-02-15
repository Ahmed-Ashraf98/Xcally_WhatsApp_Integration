from fastapi import APIRouter, FastAPI, Body, Query, Request, Response, status, File, UploadFile, Form, HTTPException
from typing import Annotated, Any
from root.global_vars import *
from root.services.xcally_tools import xcally_services as xc_services
from root.services.whatsapp_tools import whatsapp_services as wa_services

router = APIRouter(prefix="/xcally_webhook",tags=["xcally"])

@router.post("")
async def xcally_new_message_from_agent(request:Request):

    result_of_request = await request.json()
    message_obj = await xc_services.xc_extract_event_message_details(result_of_request)
    # {"customer_details": contact_details, "message_type": msg_type, "msg_is_media": msg_is_media,"message_data": message_data}

    send_msg_to_wa_customer_response = {}

    customer_details = message_obj["customer_details"]
    message_type = message_obj["message_type"]

    if message_obj["msg_is_media"]:

        # Download the attachment first
        attachment_id = message_obj["message_data"]["AttachmentId"]
        media_download_response = await xc_services.xc_download_attachment(attachment_id)
        file = None

        if media_download_response.get("status") == "success" :

            file = open(media_download_response.get("media_local_path"),"rb")
            # Upload image into the Meta
            media_id_response = await wa_services.wa_upload_media_handler(message_obj["message_data"]["body"],file,message_obj["message_type"])
            print(media_id_response["data"])
            media_id = media_id_response["data"]["id"]

            # Use the returned Media Id to send the message

            ## Send the message to the customer ( Meta API )
            send_msg_to_wa_customer_response = await wa_services.wa_send_message_to_whatsapp_user(
                customer_phone_num=customer_details["phone"],
                msg_type=message_type,
                media_id=media_id
            )

    else:
        # if not media
        send_msg_to_wa_customer_response = await wa_services.wa_send_message_to_whatsapp_user(
            customer_phone_num=customer_details["phone"],
            msg_type=message_type,
            message_content=message_obj["message_data"]["body"]
        )
    print(send_msg_to_wa_customer_response)
    return send_msg_to_wa_customer_response

