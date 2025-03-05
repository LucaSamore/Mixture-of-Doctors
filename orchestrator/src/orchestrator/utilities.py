from loguru import logger
from enum import Enum


class PromptTemplate(Enum):
    PLANNING = "./orchestrator/src/orchestrator/prompts/planning.md"


logger.add("./orchestrator/logs/orchestrator.log", rotation="10 MB")
