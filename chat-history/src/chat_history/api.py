from chat_history.database import get_database
from chat_history.collection_model import ConversationModel, ConversationItem
from chat_history.services import ConversationService
from fastapi import APIRouter, HTTPException, Depends
from loguru import logger


router = APIRouter()


@router.post("/", response_model=ConversationModel, status_code=200)
async def add_conversation_item(username: str, conversation_item: ConversationItem, db=Depends(get_database)):
    logger.info(f"Adding conversation item for user: {username}")
    service = ConversationService(db)
    result = await service.add_conversation_item(username, conversation_item)
    logger.success(f"Successfully added conversation item for user: {username}")
    return result


@router.get("/{username}", response_model=ConversationModel)
async def get_user_conversation(username: str, db=Depends(get_database)):
    logger.info(f"Getting conversation for user: {username}")
    service = ConversationService(db)
    conversations = await service.get_conversation_by_username(username)

    if not conversations:
        logger.warning(f"Conversation not found for user: {username}")
        raise HTTPException(status_code=404, detail="Conversation not found")

    logger.success(f"Retrieved conversation for user: {username}")
    return conversations


@router.delete("/{username}", status_code=204)
async def delete_user_conversation(username: str, db=Depends(get_database)):
    logger.info(f"Deleting conversation for user: {username}")
    conversation_service = ConversationService(db)
    deleted = await conversation_service.delete_conversation_by_username(username)
    
    if not deleted:
        logger.warning(f"Conversation not found for user: {username}")
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    logger.success(f"Successfully deleted conversation for user: {username}")