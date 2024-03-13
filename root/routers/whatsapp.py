from fastapi import APIRouter, Body, Request, Response
from typing import Annotated, Any
from fastapi.responses import PlainTextResponse
from root.global_vars import *
from root.services.whatsapp_services import wa_new_message_handler,wa_check_event_type,wa_msg_is_valid


router = APIRouter(prefix="/wa_webhook",tags=["whatsapp"])


@router.post("",summary="Endpoint for listening to any eve")
async def wa_new_message_from_user(wa_msg_data:Annotated[dict[str,Any],Body()]):

    # check if the event from the user or from the server
    event_type = wa_check_event_type(wa_msg_data)

    if event_type == "server_event":
        # for example 'status' changed to 'delivered' or 'sent' or 'read'
        print("*" * 50)
        print("JUST SERVER MESSAGE")
        print("*" * 50)
        return None

    if not wa_msg_is_valid(wa_msg_data):
        # for example react on the message or sending stickers
        print("*" * 50)
        print("UNSUPPORTED MESSAGE CONTENT")
        print("*" * 50)
        return None

    wa_new_message_handler.delay(wa_msg_data)
    return {"message":"WA Tasks has been started ....."}


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
