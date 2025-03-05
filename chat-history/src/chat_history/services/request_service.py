from typing import Optional
from chat_history.models.request import ConversationModel, ConversationItem


class ConversationService:
    """
    Service for managing user conversations with transaction support
    """

    def __init__(self, db):
        self.db = db
        self.collection = db.conversations

    async def add_conversation_item(
        self, username: str, conversation_item: ConversationItem
    ) -> ConversationModel:
        """
        Add a new conversation item to the existing conversation

        Args:
            username: The username of the user to whom the conversation item belongs
            conversation_item: The conversation item to add

        Returns:
            ConversationModel: The updated conversation with the new item
        """

        async def transaction_callback(session):
            existing_conversation = await self.collection.find_one(
                {"username": username}, session=session
            )

            if existing_conversation:
                existing_conversation = ConversationModel(**existing_conversation)
                existing_conversation.conversation.append(conversation_item)
                conversation_dict = existing_conversation.model_dump()
            else:
                conversation_dict = ConversationModel(
                    username=username, conversation=[conversation_item]
                ).model_dump()

            await self.collection.update_one(
                {"username": username},
                {"$set": conversation_dict},
                upsert=True,
                session=session,
            )

            return conversation_dict

        async with await self.db.client.start_session() as session:
            async with session.start_transaction():
                conversation_dict = await transaction_callback(session)

                return ConversationModel(**conversation_dict)

    async def get_conversation_by_username(
        self, username: str
    ) -> Optional[ConversationModel]:
        """
        Get the conversation history of a user

        Args:
            username: Username of the user whose conversation history to retrieve

        Returns:
            Optional[ConversationModel]: The conversation history, or None if not found
        """
        doc = await self.collection.find_one({"username": username})

        if doc:
            doc.pop("_id", None)
            return ConversationModel(**doc)

        return None
