from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from .planning import reason, act, ChatbotQuery
from .exceptions import PlanningException
from .utilities import (
    init_kafka_producer,
    init_redis_client,
    init_groq_client,
    get_kafka_producer,
    get_redis_client,
    get_llm_groq,
)
from aiokafka import AIOKafkaProducer
from groq import AsyncGroq
import redis.asyncio as redis


@asynccontextmanager
async def lifespan(_: FastAPI):
    kafka_producer = await init_kafka_producer()
    redis_client = await init_redis_client()
    llm_groq = await init_groq_client()

    await kafka_producer.start()

    app.state.kafka_producer = kafka_producer
    app.state.redis_client = redis_client
    app.state.llm_groq = llm_groq

    yield

    await kafka_producer.stop()
    await redis_client.close()
    await llm_groq.close()


app = FastAPI(
    title="Orchestrator's REST API",
    description="This API orchestrates the planning and execution of chatbot queries.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(PlanningException)
async def planning_exception_handler(_: Request, exc: PlanningException):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.post("/", status_code=204)
async def handle_request(
    request: ChatbotQuery,
    kafka_producer: AIOKafkaProducer = Depends(get_kafka_producer),
    redis_client: redis.Redis = Depends(get_redis_client),
    llm_groq: AsyncGroq = Depends(get_llm_groq),
):
    outcome = await reason(request, llm_groq)
    await act(outcome, request, kafka_producer, redis_client, llm_groq)


@app.get("/health", status_code=200)
async def healthcheck():
    return JSONResponse(status_code=200, content={"status": "UP"})
