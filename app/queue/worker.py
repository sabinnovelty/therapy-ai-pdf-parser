from dotenv import load_dotenv
from app.processors.factory import ProcessorFactory
import asyncio

# Load .env first so MONGO_URI / MONGO_URI_WORKER (with auth) are set before db is imported
load_dotenv()

from app.db.collections.files import files_collection
from bson import ObjectId

async def _process_file_async(id: str, file_path: str):
    print(f"Worker:Processing file: {id}")
    await files_collection.update_one({"_id": ObjectId(id)}, {"$set": {"status": "processing"}})
    
    processor = ProcessorFactory.get_processor("pdf_text")
    processor_result = await processor.process(id, file_path)
    try:
        print(f"Processing file: {id}")
    except Exception as e:
        await files_collection.update_one({"_id": ObjectId(id)}, {"$set": {"status": "failed", "error": str(e)}})

def process_file(id: str, file_path: str):
    """Sync entrypoint for RQ: runs async work via asyncio.run()."""
    asyncio.run(_process_file_async(id, file_path))