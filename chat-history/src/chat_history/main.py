from chat_history.database import connect_to_mongo, close_mongo_connection
from chat_history import api
from chat_history.mongoUI import router as mongo_ui_router
from fastapi import FastAPI
import uvicorn

app = FastAPI(
    title="Chat History API",
    description="API per la gestione della cronologia delle chat con interfaccia MongoDB",
    version="1.0.0"
)

app.include_router(api.router, prefix="/requests")
app.include_router(mongo_ui_router, prefix="/admin")

app.add_event_handler("startup", connect_to_mongo)
app.add_event_handler("shutdown", close_mongo_connection)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)