from fastapi import APIRouter
from fastapi.responses import RedirectResponse
import os

router = APIRouter(tags=["mongo-UI"])

MONGO_UI_HOST = os.environ.get("MONGO_UI_HOST", "localhost")
MONGO_UI_PORT = os.environ.get("MONGO_UI_PORT", "8081")

@router.get("/mongo-ui")
async def redirect_to_mongo_ui():
    return RedirectResponse(url=f"http://{MONGO_UI_HOST}:{MONGO_UI_PORT}")
