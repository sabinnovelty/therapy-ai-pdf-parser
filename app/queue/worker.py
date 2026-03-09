from dotenv import load_dotenv
from app.processors.factory import ProcessorFactory
import asyncio

# Load .env first so MONGO_URI / MONGO_URI_WORKER (with auth) are set before db is imported
load_dotenv()

from app.db.collections.files import files_collection
from bson import ObjectId

async def _process_file_async(id: str, file_path: str):
    from pathlib import Path
    print(f"Worker:Processing file: {id}")
    await files_collection.update_one({"_id": ObjectId(id)}, {"$set": {"status": "processing"}})
    # Resolve to absolute path so we can open the PDF and save page images in the same directory
    abs_path = str(Path(file_path).resolve())
    if not Path(abs_path).exists():
        await files_collection.update_one(
            {"_id": ObjectId(id)},
            {"$set": {"status": "failed", "error": f"File not found: {abs_path}"}},
        )
        return
    processor = ProcessorFactory.get_processor("pdf_text")
    try:
        processor_result = await processor.process_pdf(id, abs_path)
        n_visits = len(processor_result.get("visits", []))
        n_images = sum(len(v.get("pages", [])) for v in processor_result.get("visits", []))
        print(f"Processing file: {id} -> {n_visits} visits, {n_images} page images saved")
    except Exception as e:
        await files_collection.update_one(
            {"_id": ObjectId(id)},
            {"$set": {"status": "failed", "error": str(e)}},
        )
        raise

def process_file(id: str, file_path: str):
    """Sync entrypoint for RQ: runs async work via asyncio.run()."""
    asyncio.run(_process_file_async(id, file_path))