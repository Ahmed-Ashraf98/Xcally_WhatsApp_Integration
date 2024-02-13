from fastapi import APIRouter, FastAPI, Body, Query, Request, Response, status, File, UploadFile, Form, HTTPException
from typing import Annotated, Any

router = APIRouter(prefix="/xcally_webhook",tags=["xcally"])

xcally_key = "Sana"


@router.get("")
async def xcally_verification(request:Request, response : Response):

    print(request)
    print(response)




