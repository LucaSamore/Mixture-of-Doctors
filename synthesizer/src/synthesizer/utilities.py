from kafka import KafkaConsumer
from dotenv import load_dotenv
import os
import json


load_dotenv()

consumer = KafkaConsumer(
    bootstrap_servers=os.getenv("KAFKA_BROKER"),
    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
)