from fastapi import APIRouter, FastAPI, Body, Query, Request, Response, status, File, UploadFile, Form, HTTPException
from typing import Annotated, Any
from fastapi.responses import PlainTextResponse
from root.services.whatsapp_tools import whatsapp_services as wa_services
from root.services.xcally_tools import xcally_services as xc_services
from root.globals import *

router = APIRouter(prefix="/wa_webhook",tags=["whatsapp"])

@router.post("",summary="Endpoint for listening to any eve")
async def wa_new_message_from_user(wa_msg_data:Annotated[dict[str,Any],Body()]):

    # check if the event from the user or from the server

    event_type = await wa_services.wa_check_event_type(wa_msg_data)

    if event_type == "server_event":
        # for example 'status' changed to 'delivered' or 'sent' or 'read'
        print("*" * 50)
        print("JUST SERVER MESSAGE")
        print("*" * 50)
        return None

    # 1) Check if the message is media or just a text and return the result as follows :
    # {"sender_details": contact_obj, "message_type":message_type, "msg_is_media":msg_is_media, "message_data":message_data}

    message_obj = await wa_services.wa_get_received_messages_details(wa_msg_data)


    # 2) If media:

    if message_obj.get("msg_is_media"):

        msg_type = message_obj.get("message_type")
        media_id = message_obj.get("message_data").get("id")
        # 2.A =>  Download this media, and get the result as follows :
        # {"status":"success","media_local_path":full_media_path,"message":"The media has been downloaded successfully"}
        media_download_response = await wa_services.wa_download_media(media_id)
        # {"status": "success", "media_local_path": <media_local_storage_path>, "message": "The media has been downloaded successfully"}

        if media_download_response.get("status") == "success" :

            # 2.B =>  Open the file and send it to the XCally Upload Media API , and return the media id
            file = open(media_download_response.get("media_local_path"),"rb")
            # Missing to upload the Media

            # 2.C =>  Send the message to the XCally with the file media and (check if message sent to return the result)
            message_send_response = await xc_services.send_message_to_xcally_channel(
                message_obj.get("sender_details"),
                msg_type=msg_type,
                message_content=message_obj.get("message_data"),
                file=file
            )
            print("~" * 50)
            print(message_send_response)
            print("~" * 50)

    else: # Not media message
        # 3) Send the message to the XCally and (check if message sent to return the result)
        message_send_response = await xc_services.send_message_to_xcally_channel(
            message_obj.get("sender_details"),
            message_content=message_obj.get("message_data")
        )
        print("~" * 50)
        print(message_send_response)
        print("~" * 50)

    return wa_msg_data



@router.get("")
async def wa_verification(request:Request, response : Response):
    # Parse params from the webhook verification request
    mode = request.query_params["hub.mode"]
    token = request.query_params["hub.verify_token"]
    challenge = request.query_params["hub.challenge"]

    # Check if a token and mode were sent by meta
    if mode and token:
        if mode == "subscribe" and token == wa_verify_token:
            # Respond with 200 OK and challenge token from the request
            print("WEBHOOK_VERIFIED")
            return PlainTextResponse(content=challenge, status_code=200)
        else:
            # Responds with '403 Forbidden' if verify tokens do not match
            print("WEBHOOK_ERROR")
            response.status_code = 403

    print(request.json())