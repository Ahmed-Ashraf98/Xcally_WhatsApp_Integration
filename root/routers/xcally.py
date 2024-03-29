from fastapi import APIRouter, Request
from root.services import xcally_services as xc_services
router = APIRouter(prefix="/xcally_webhook",tags=["xcally"])

@router.post("")
async def xcally_new_message_from_agent(request:Request):

    result_of_request = await request.json()
    xc_services.xc_new_message_handler.delay(result_of_request)
    return {"message": "XCally Tasks has been started ....."}

