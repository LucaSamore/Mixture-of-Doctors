from kafka import KafkaProducer
from dotenv import load_dotenv
import os
import json

load_dotenv()

producer = KafkaProducer(
    bootstrap_servers=os.getenv('KAFKA_BROKER'),
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
)