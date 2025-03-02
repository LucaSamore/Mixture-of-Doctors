from motor.motor_asyncio import AsyncIOMotorClient
import os

# Global variables for the client and the database
mongodb_url: str = os.getenv(
    "MONGODB_URL", "mongodb+srv://robertomitugno:123@databasemod.gnszi.mongodb.net/"
)
database_name: str = os.getenv("DATABASE_NAME", "Mixture-of-Doctors")

client: AsyncIOMotorClient
db = None


async def get_database():
    """
    Dependency to get the database instance
    """
    return db


async def connect_to_mongo():
    """
    Connect to the MongoDB database when the application starts
    """
    global client, db
    client = AsyncIOMotorClient(mongodb_url)
    db = client[database_name]

    try:
        await client.admin.command("ping")
        print(f"Connected to MongoDB at {mongodb_url}")
        print(f"Using database: {database_name}")
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")


async def close_mongo_connection():
    """
    Close the MongoDB database connection when the application shuts down
    """
    global client
    if client:
        client.close()
        print("MongoDB connection closed")
