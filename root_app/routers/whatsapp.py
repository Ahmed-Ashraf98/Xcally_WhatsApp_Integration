from fastapi import APIRouter, FastAPI, Body, Query, Request, Response, status, File, UploadFile, Form, HTTPException
from typing import Annotated, Any
from fastapi.responses import PlainTextResponse
from root_app.services.whatsapp_tools import whatsapp_services as wa_service

router = APIRouter(prefix="/wa_webhook",tags=["whatsapp"])

wa_verify_token = "Sana"
phone_number_id = "209325405605976"
access_token = "EAARxAciB8DkBO89zuix7B5WE9ZBUdhyZASkavn9XueUM6ajocrQ3DYNSlG3OmoKxKc2pGV8CbZBtZCMa54ihtsDyTDz2FZAdcwJKaMVcb1iMhq3yU1kQIqZCvKzvRGYV6dwXQHB6qoWwE41Gi3BxRZCnidoaDbPGsZA4YNRh0NiM0VZBC1sQVrGEd1HsplajAJ40gsWvh1hwFopV0rfKDxXbj00fmQhQZD"
wa_request_url = "https://graph.facebook.com/v19.0/"+phone_number_id+"/messages"
wa_media_url = "https://graph.facebook.com/v19.0/"+phone_number_id+"/media"


@router.post("/",summary="Endpoint for listening to any eve")
async def wa_new_message_from_user(wa_msg_data:Annotated[dict[str,Any],Body()]):

    # check if the event from the user or from the server

    event_type = await wa_service.wa_check_event_type(wa_msg_data)

    if event_type == "server_event":
        # for example 'status' changed to 'delivered' or 'sent' or 'read'
        print("*" * 50)
        print("JUST SERVER MESSAGE")
        print("*" * 50)
        return None

    # 1) Check if the message is media or just a text and return the result as follows :
    # {"sender_details": contact_obj, "message_type":message_type, "msg_is_media":msg_is_media, "message_data":message_data}

    message_obj = await wa_service.wa_get_received_messages_details(wa_msg_data)


    # 2) If media:

    if message_obj.get("msg_is_media"):

        msg_type = message_obj.get("message_type")
        media_id = message_obj.get("message_data").get("id")
        # 2.A =>  Download this media, and get the result as follows :
        # {"status":"success","media_local_path":full_media_path,"message":"The media has been downloaded successfully"}
        media_download_response = await wa_service.wa_download_media(media_id)
        # {"status": "success", "media_local_path": <media_local_storage_path>, "message": "The media has been downloaded successfully"}

        if(media_download_response.get("status") == "success" ):
            pass
        # 2.B =>  Open the file and send it to the XCally Upload Media API , and return the media id
        file = open(media_download_response.get("media_local_path"),"rb")
        # Missing to upload the Media

        # 2.C =>  Send the message to the XCally with the file media and (check if message sent to return the result)
        message_send_response = await wa_service.wa_send_message_to_xcally(message_obj.get("sender_details"),msg_type=msg_type,message_content=message_obj.get("message_data"),media_file=file)
        print("~" * 50)
        print(message_send_response)
        print("~" * 50)

    else:# Not media message
        # 3) Send the message to the XCally and (check if message sent to return the result)
        message_send_response = await wa_service.wa_send_message_to_xcally(message_obj.get("sender_details"), message_content=message_obj.get("message_data"))
        print("~" * 50)
        print(message_send_response)
        print("~" * 50)

    return wa_msg_data



@router.get("/")
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
            response.status_code = 403


