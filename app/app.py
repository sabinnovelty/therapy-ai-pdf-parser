from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.exceptions import RequestValidationError
from dotenv import load_dotenv

from app.utils.logger import configure_logger, get_logger
from app.utils.exception_handlers import (
    validation_exception_handler,
    http_exception_handler,
    general_exception_handler,
)
from app.core.config import configure_rag_settings, validate_rag_environment
from app.core.storage import setup_storage
from app.core.data import STORAGE_DIR

from uuid import uuid4
import os

from app.utils.file import save_to_disk

from app.db.collections.files import files_collection,FileSchema
from app.queue.queue import q
from app.queue.worker import process_file

# Load environment variables from .env file
load_dotenv()

# Configure structured logging
configure_logger(
    log_level="INFO",
    enable_json=False,  # Set to True for CloudWatch JSON logs
    cloudwatch_mode=False,  # Set to True when deploying to AWS
)

logger = get_logger(__name__)

from app.api.endpoints.summarizer_router import router as summarizer_router
from app.api.endpoints.rag_router import router as rag_router

app = FastAPI(
    title="Therapy AI",
    description="""
## Therapy AI

AI-powered summarization and RAG service for healthcare case notes.

### Features

* **Case Note Summarization** - Generate AI-powered summaries of patient case notes
* **Healthcare Advocacy RAG** - Query healthcare policies, plans, and regulations
* **Role-based Summaries** - Tailored summaries based on user roles
* **Flexible Summarization Types** - Support for full and unread note summarization

### Authentication

Currently, no authentication is required for API access.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
    ],
    contact={
        "name": "Therapy AI Support",
        "email": "support@therapyai.com",
    },
    license_info={
        "name": "Proprietary",
    },
)

# Initialize storage directories
setup_storage()

# Validate and initialize RAG configuration
try:
    validate_rag_environment()
    configure_rag_settings()
    logger.info("RAG configuration initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize RAG configuration: {str(e)}", exc_info=True)
    # Continue startup but RAG endpoints may fail

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Register exception handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)


@app.get(
    "/",
    tags=["Health"],
    summary="Root Endpoint",
    description="Welcome endpoint that confirms the API is running.",
)

async def root():
    """Return a welcome message confirming the API is running."""
    return {"message": "Welcome to Therapy AI API"}


@app.get(
    "/health",
    tags=["Health"],
    summary="Health Check",
    description="Check if the API service is healthy and responding.",
    responses={
        200: {
            "description": "Service is healthy",
            "content": {
                "application/json": {
                    "example": {"status": "healthy"}
                }
            }
        }
    }
)

async def health_check():
    """Return the health status of the API service."""
    return {"status": "healthy"}


@app.post('/upload', tags=["Therapy Parser"])
async def upload(file: UploadFile):
    """Upload a PDF. File is saved to storage/uploads/<file_id>/. An RQ worker must be running to process the PDF and save page images (visit-1-page-1.png, etc.) in the same folder. Poll GET /files/{file_id}/result for status and result."""
    try:
        filename = file.filename or "upload"
        extension = os.path.splitext(filename)[1].lstrip(".").lower() or ""
        if extension != "pdf":
            raise HTTPException(status_code=400, detail="Only PDF files are accepted")
        doc: FileSchema = {"name": filename, "status": "saving", "extension": extension}
        db_file = await files_collection.insert_one(document=doc)
        # Use absolute path so the RQ worker (possibly different cwd) can find the file and save page images next to it
        dir_path = (STORAGE_DIR / "uploads" / str(db_file.inserted_id)).resolve()
        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = str(dir_path / filename)
        await save_to_disk(file=await file.read(), file_path=file_path)

        job = q.enqueue(process_file, str(db_file.inserted_id), file_path)
        await files_collection.update_one({"_id": db_file.inserted_id}, {"$set": {"status": "queued"}})

        return {"file_id": str(db_file.inserted_id)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/files/{file_id}/result", summary="Get processing result by file ID" ,tags=["Therapy Parser"])
async def get_file_result(file_id: str):
    """Return the stored processing result for an uploaded file, if available."""
    from bson import ObjectId
    try:
        oid = ObjectId(file_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid file_id")
    doc = await files_collection.find_one({"_id": oid}, projection={"name": 1, "status": 1, "extension": 1, "result": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="File not found")
    return {
        "file_id": file_id,
        "name": doc.get("name"),
        "status": doc.get("status"),
        "extension": doc.get("extension"),
        "result": doc.get("result"),
    }

@app.get('/documents', tags=["Therapy Parser"])
async def get_all_documents():
    """Return all documents from the database."""
    documents = await files_collection.find().to_list(length=None)
    for doc in documents:
        doc["_id"] = str(doc["_id"])
    return documents


@app.get("/files/{file_id}/visit/{visit_number}", tags=["Therapy Parser"])
async def get_visit_pages(file_id: str, visit_number: int):
    """Return one visit's data and pages for a file. Use visit_number from result.visits[].visitNumber."""
    from bson import ObjectId
    try:
        oid = ObjectId(file_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid file_id")
    doc = await files_collection.find_one(
        {"_id": oid},
        projection={"name": 1, "status": 1, "result": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="File not found")
    result = doc.get("result")
    if not result or not isinstance(result.get("visits"), list):
        raise HTTPException(status_code=404, detail="No visits data; file may still be processing.")
    for v in result["visits"]:
        if v.get("visitNumber") == visit_number:
            return {
                "file_id": file_id,
                "document_name": doc.get("name"),
                "visitNumber": v.get("visitNumber"),
                "visitDate": v.get("visitDate"),
                "pageCount": v.get("pageCount", 0),
                "pages": v.get("pages", []),
            }
    raise HTTPException(status_code=404, detail=f"Visit {visit_number} not found for this file.")


@app.get("/files/{file_id}/pages/{path:path}", tags=["Therapy Parser"])
async def serve_visit_page_image(file_id: str, path: str):
    """Serve a page image for a file (e.g. visit-17-page-1.png). Path must be a single filename under pages/."""
    from bson import ObjectId
    try:
        ObjectId(file_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid file_id")
    # Restrict to filename only (no slashes) to avoid path traversal
    if "/" in path or path.startswith(".."):
        raise HTTPException(status_code=400, detail="Invalid path")
    file_path = (STORAGE_DIR / "uploads" / file_id / "pages" / path).resolve()
    root = (STORAGE_DIR / "uploads" / file_id).resolve()
    if not file_path.is_file() or not str(file_path).startswith(str(root)):
        raise HTTPException(status_code=404, detail="Page image not found")
    return FileResponse(file_path, media_type="image/png")


