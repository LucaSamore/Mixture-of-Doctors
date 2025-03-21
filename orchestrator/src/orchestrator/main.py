from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from .planning import reason, act, ChatbotQuery
from .exceptions import PlanningException
import httpx
from .configurations import chat_history_url

app = FastAPI()


@app.exception_handler(PlanningException)
async def planning_exception_handler(_: Request, exc: PlanningException):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.post("/", status_code=204)
async def handle_request(request: ChatbotQuery):
    outcome = await reason(request)
    await act(outcome, request)


@app.get("/health", status_code=200)
async def healthcheck():
    return JSONResponse(status_code=200, content={"status": "UP"})


@app.get("/", status_code=200)
async def test():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{chat_history_url}test",
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return JSONResponse(status_code=500, content={"detail": str(e)})