import motor.motor_asyncio
from pymongo import ASCENDING
from bson import ObjectId
import os

# Get MongoDB connection string from environment variable
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "isstow")

client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
db = client[MONGODB_DB_NAME]

# Create collections
items_collection = db.items
containers_collection = db.containers
placements_collection = db.placements
logs_collection = db.logs
waste_collection = db.waste
simulation_collection = db.simulation

# Create indexes
async def init_db():
    # Create an index on the itemId field for items collection
    await items_collection.create_index([("itemId", ASCENDING)], unique=True)
    # Create an index on the containerId field for containers collection
    await containers_collection.create_index([("containerId", ASCENDING)], unique=True)
    # Create an index on itemId for placements collection
    await placements_collection.create_index([("itemId", ASCENDING)], unique=True)
    # Create compound index for faster placement queries
    await placements_collection.create_index([("containerId", ASCENDING), ("itemId", ASCENDING)])
    # Create an index on timestamp for logs collection
    await logs_collection.create_index([("timestamp", ASCENDING)])
    # Create an index on itemId for waste collection
    await waste_collection.create_index([("itemId", ASCENDING)], unique=True)
    # Create an index on timestamp for simulation collection
    await simulation_collection.create_index([("timestamp", ASCENDING)])
