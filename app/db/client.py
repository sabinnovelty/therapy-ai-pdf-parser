from pymongo import AsyncMongoClient
import os

mongo_client: AsyncMongoClient = AsyncMongoClient(os.getenv("MONGO_URI"))