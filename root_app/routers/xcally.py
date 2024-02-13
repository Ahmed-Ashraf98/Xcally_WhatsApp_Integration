from fastapi import APIRouter, FastAPI, Body, Query, Request, Response, status, File, UploadFile, Form, HTTPException
from typing import Annotated, Any

router = APIRouter(prefix="/xcally_webhook",tags=["xcally"])

