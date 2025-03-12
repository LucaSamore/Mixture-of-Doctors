from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from .planning import reason, act, PlanningException, ChatbotQuery


app = FastAPI()


@app.exception_handler(PlanningException)
async def planning_exception_handler(_: Request, exc: PlanningException):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.post("/", status_code=204)
async def handle_request(request: ChatbotQuery):
    outcome = await reason(request)
    await act(outcome, request)
