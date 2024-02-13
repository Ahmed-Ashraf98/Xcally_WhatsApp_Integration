
from fastapi import FastAPI

from root.routers.whatsapp import router as wa_router
from root.routers.xcally import router as xcally_router

app = FastAPI()

app.include_router(wa_router)
app.include_router(xcally_router)

