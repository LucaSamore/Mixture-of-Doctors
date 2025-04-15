from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClientSession
from chat_history.collection_model import ConversationModel, ConversationItem
from loguru import logger


class ConversationService:
    def __init__(self, database):
        self.database = database
        self.conversation_collection = database.conversations

    async def add_conversation_item(
        self, username: str, conversation_item: Optional[ConversationItem] = None
    ) -> ConversationModel:
        logger.info(
            f"Starting transaction to add conversation item for user: {username}"
        )
        async with await self.database.client.start_session() as session:
            async with session.start_transaction():
                updated_conversation = await self._update_conversation_transaction(
                    session, username, conversation_item
                )
                logger.info(f"Transaction completed successfully for user: {username}")
                return ConversationModel(**updated_conversation)

    async def _update_conversation_transaction(
        self,
        session: AsyncIOMotorClientSession,
        username: str,
        conversation_item: Optional[ConversationItem] = None,
    ) -> dict:
        existing_conversation = await self.conversation_collection.find_one(
            {"username": username}, session=session
        )

        if existing_conversation:
            logger.info(f"Updating existing conversation for user: {username}")
            conversation_model = ConversationModel(**existing_conversation)
            if conversation_item:
                conversation_model.conversation.append(conversation_item)
        else:
            logger.info(f"Creating new conversation for user: {username}")
            conversation = [] if conversation_item is None else [conversation_item]
            conversation_model = ConversationModel(
                username=username, conversation=conversation
            )

        updated_conversation_dict = conversation_model.model_dump()

        await self.conversation_collection.update_one(
            {"username": username},
            {"$set": updated_conversation_dict},
            upsert=True,
            session=session,
        )

        return updated_conversation_dict

    async def get_conversation_by_username(
        self, username: str
    ) -> Optional[ConversationModel]:
        logger.info(f"Fetching conversation for user: {username}")
        conversation_document = await self.conversation_collection.find_one(
            {"username": username}
        )
        if conversation_document:
            conversation_document.pop("_id", None)
            return ConversationModel(**conversation_document)
        return None

    async def delete_conversation_by_username(self, username: str) -> bool:
        logger.info(f"Attempting to delete conversation for user: {username}")
        delete_result = await self.conversation_collection.delete_one(
            {"username": username}
        )
        return delete_result.deleted_count > 0
