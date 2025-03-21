from loguru import logger
from pydantic import BaseModel
from typing import Dict
from synthesizer.utilities import consumer
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

                        #await handle_rag_response(response)

                    except Exception as e:
                        logger.error(f"Error processing message: {str(e)}")

    except Exception as e:
        logger.error(f"Consumer error: {e}")
    finally:
        logger.info("Consumer stopped")