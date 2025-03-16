from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
import os

load_dotenv()

router = APIRouter(tags=["mongo-UI"])

MONGO_UI_HOST = os.getenv("MONGO_UI_HOST")
MONGO_UI_PORT = os.getenv("MONGO_UI_PORT")

@router.get("/mongo-ui")
async def redirect_to_mongo_ui():
    return RedirectResponse(url=f"http://{MONGO_UI_HOST}:{MONGO_UI_PORT}")
