import shutil
from fastapi import UploadFile
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import StorageContext
from app.core.storage import get_storage_client, STORAGE_DIR

def setup_storage():
    """Initializes the directory structure."""
    folders = ["raw_uploads", "vector_db", "markdown_cache"]
    for folder in folders:
        (STORAGE_DIR / folder).mkdir(parents=True, exist_ok=True)

async def save_upload(file: UploadFile, tenant_id: str) -> str:
    tenant_path = STORAGE_DIR / "raw_uploads" / tenant_id
    tenant_path.mkdir(parents=True, exist_ok=True)
    
    file_path = tenant_path / file.filename
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return str(file_path)

def get_vector_store(collection_name: str = "healthcare_index"):
    """
    Get or create a ChromaDB vector store collection.
    
    Uses consistent collection name "healthcare_index" across the application.
    Storage backend is determined by core/storage.py configuration.
    
    Args:
        collection_name: Name of the collection to use (defaults to "healthcare_index")
        
    Returns:
        ChromaVectorStore instance
    """
    db = get_storage_client()
    chroma_collection = db.get_or_create_collection(collection_name)
    return ChromaVectorStore(chroma_collection=chroma_collection)

def get_storage_context(vector_store):
    """
    Create a StorageContext from a vector store.
    
    Args:
        vector_store: ChromaVectorStore instance
        
    Returns:
        StorageContext instance
    """
    return StorageContext.from_defaults(vector_store=vector_store)

