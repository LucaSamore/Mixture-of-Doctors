from chat_history.database import connect_to_mongodb, close_mongodb_connection
from chat_history import api
from chat_history.mongoUI import router as mongo_ui_router
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from loguru import logger
import uvicorn

logger.remove()
logger.add("./logs/chat-history.log", rotation="10 MB")

app = FastAPI(
    title="Chat History API",
    description="API to store and retrieve chat history",
    version="1.0.0",
)

app.include_router(api.router, prefix="/requests")
app.include_router(mongo_ui_router, prefix="/admin")

app.add_event_handler("startup", connect_to_mongodb)
app.add_event_handler("shutdown", close_mongodb_connection)


@app.get("/health", status_code=200)
async def healthcheck():
    return JSONResponse(status_code=200, content={"status": "up"})


if __name__ == "__main__":
    logger.info("Starting Chat History API server")
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
