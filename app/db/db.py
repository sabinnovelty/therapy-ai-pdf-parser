from app.db.client import mongo_client


database = mongo_client.get_database("therapy-ai")