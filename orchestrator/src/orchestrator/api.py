from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .planning import reason, act

class Request(BaseModel):
    user_id: str
    query: str

app = FastAPI()

@app.post("/", status_code=204)
async def handle_request(request: Request):
    pass
