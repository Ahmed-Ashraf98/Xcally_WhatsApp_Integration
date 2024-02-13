from typing import Annotated, Any
from fastapi import APIRouter
from fastapi import FastAPI,Body, Query ,Request,Response , status,File,UploadFile, Form,HTTPException
from pydantic import BaseModel
from fastapi.responses import PlainTextResponse
import httpx
from root_app.routers.whatsapp import router as wa_router
from root_app.routers.xcally import router as xcally_router

app = FastAPI()

app.include_router(wa_router)
app.include_router(xcally_router)

