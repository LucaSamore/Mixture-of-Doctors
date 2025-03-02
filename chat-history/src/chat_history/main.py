from chat_history.database import connect_to_mongo, close_mongo_connection
from chat_history.endpoints import requests
from fastapi import FastAPI
import uvicorn

app = FastAPI()

app.include_router(requests.router, prefix="/requests")

app.add_event_handler("startup", connect_to_mongo)
app.add_event_handler("shutdown", close_mongo_connection)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
