from loguru import logger
from pydantic import BaseModel
from typing import Dict
from .utilities import llm, consumer, prepare_prompt
import json
import asyncio
import json



active_queries: Dict[str, Dict] = {}
consumer_kafka_running = False
consumer_task = None


class RagResponse(BaseModel):
    user_id: str
    disease: str
    original_query: str
    response: str
    stream: bool
    number: int
    total: int


async def start_consumer():
    global consumer_kafka_running, consumer_task
    
    if consumer_kafka_running:
        return
    
    consumer_kafka_running = True
    consumer_task = asyncio.create_task(reader_kafka())


async def stop_consumer():
    global consumer_kafka_running, consumer_task
    
    if consumer_kafka_running and consumer_task:
        consumer_kafka_running = False
        consumer.close()
        await consumer_task


async def reader_kafka():
    global consumer_kafka_running
    
    try:
        consumer.subscribe(['synthesizer'])
        
        while consumer_kafka_running:
            consume_messages = consumer.poll(timeout_ms=1)
            
            if consume_messages is None:
                continue  
                    
            for partition, messages in consume_messages.items():
                for message in messages:
                    if message.error() is not None:
                            logger.error(f"Consumer error: {message.error()}")
                            continue  
                    try:                          
                        value = json.loads(message.value().decode('utf-8'))
                        response = RagResponse(**value)
                        logger.info(f"Received message: {response}")

                        await handle_rag_response(response)

                    except Exception as e:
                        logger.error(f"Error processing message: {str(e)}")

    except Exception as e:
        logger.error(f"Consumer error: {e}")
    finally:
        logger.info("Consumer stopped")


async def handle_rag_response(rag_response: RagResponse):
    user_id = rag_response.user_id
    
    if user_id not in active_queries:
        active_queries[user_id] = {
            "original_query": rag_response.original_query,
            "responses": {},
            "received_numbers": set(),
            "total": rag_response.total,
            "stream": rag_response.stream
        }
    
    query_data = active_queries[user_id]
    
    query_data["responses"][rag_response.disease] = rag_response.response
    query_data["received_numbers"].add(rag_response.number)
    
    if len(query_data["received_numbers"]) == query_data["total"]:
        expected_numbers = set(range(1, query_data["total"] + 1))
        if query_data["received_numbers"] == expected_numbers:
            logger.info(f"All {query_data['total']} sub-queries received for user {user_id}, synthesizing responses")
        else:
            logger.warning(f"Missing responses for user {user_id}. Expected: {expected_numbers}, Got: {query_data['received_numbers']}")


async def synthesize_responses(query_data: Dict):
    try:
        diseases_responses = []
        for disease, response in query_data.items():
            diseases_responses.append(f"### {disease.upper()} | RESPONSE:\n{response}")
        responses = "\n\n".join(diseases_responses)
        
        response = await generate_synthesis(
            query_data["original_query"], 
            responses,
            query_data["stream"]
        )
                                    
    except Exception as e:
        logger.error(f"Error during synthesis: {e}")


async def generate_synthesis(original_query: str, formatted_responses: str, stream: bool):
    params = {
        "original_query": original_query,
        "responses": formatted_responses
    }
    
    prompt = prepare_prompt(template="./synth_prompt.md", **params)
    
    response = llm.generate(model="llama3.3:latest", prompt=prompt, stream=stream)
    logger.info(f"Response synthesized {response}")
    
    return response