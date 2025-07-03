from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from .planning import reason, act, ChatbotQuery
from .exceptions import PlanningException
from .configurations import get_kafka_producer, get_redis_client, get_llm_groq
from aiokafka import AIOKafkaProducer
from groq import AsyncGroq
import redis.asyncio as redis
import os
import json


@asynccontextmanager
async def lifespan(_: FastAPI):
    kafka_producer = AIOKafkaProducer(
        bootstrap_servers=os.getenv("KAFKA_BROKER", "localhost:9092"),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await kafka_producer.start()
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=(lambda p: int(p) if p else 6379)(os.getenv("REDIS_PORT")),
        password=os.getenv("REDIS_PASSWORD", "redispassword"),
        decode_responses=True,
    )
    llm_groq = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
    app.state.kafka_producer = kafka_producer
    app.state.redis_client = redis_client
    app.state.llm_groq = llm_groq
    yield
    await kafka_producer.stop()
    await redis_client.close()
    await llm_groq.close()


app = FastAPI(lifespan=lifespan)


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
