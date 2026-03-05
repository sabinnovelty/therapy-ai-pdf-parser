import shutil
import chromadb
from pathlib import Path
from typing import Optional
from fastapi import UploadFile
from llama_index.core import StorageContext
from app.core.data import STORAGE_DIR, STORAGE_TYPE, PINECONE_API_KEY, PINECONE_INDEX_NAME, PINECONE_DIMENSION, PINECONE_METRIC, PINECONE_CLOUD, PINECONE_REGION, EMBEDDING_MODEL_DIMENSION
from app.core.config import EMBEDDING_MODEL
from app.utils.logger import get_logger

logger = get_logger(__name__)

try:
    import pinecone
    PINECONE_AVAILABLE = True
except ImportError:
    PINECONE_AVAILABLE = False
    logger.warning("Pinecone not installed. Install with: pip install pinecone-client")

STORAGE_TYPE_CHROMA = "chroma"
STORAGE_TYPE_PINECONE = "pinecone"
STORAGE_TYPE_WEAVIATE = "weaviate"
DEFAULT_STORAGE_TYPE = STORAGE_TYPE_PINECONE

def get_storage_type() -> str:
    storage_type = (STORAGE_TYPE or STORAGE_TYPE_CHROMA).lower()
    
    valid_types = [STORAGE_TYPE_CHROMA, STORAGE_TYPE_PINECONE, STORAGE_TYPE_WEAVIATE]
    if storage_type not in valid_types:
        logger.warning(
            f"Invalid STORAGE_TYPE '{storage_type}', defaulting to '{DEFAULT_STORAGE_TYPE}'"
        )
        storage_type = DEFAULT_STORAGE_TYPE
    
    return storage_type

def get_chroma_client(path: Optional[Path] = None) -> chromadb.PersistentClient:
    if path is None:
        path = STORAGE_DIR / "vector_db"
    
    db_path = str(path)
    logger.debug(f"Initializing ChromaDB client at: {db_path}")
    
    return chromadb.PersistentClient(path=db_path)

def get_pinecone_client():
    if not PINECONE_AVAILABLE:
        raise ValueError(
            "Pinecone is not installed. Install with: pip install pinecone-client"
        )
    
    api_key = PINECONE_API_KEY
    if not api_key:
        raise ValueError("PINECONE_API_KEY environment variable must be set")
    
    logger.debug("Initializing Pinecone client")
    
    pc = pinecone.Pinecone(api_key=api_key)
    
    return pc

def get_storage_client():
    storage_type = get_storage_type()
    
    if storage_type == STORAGE_TYPE_CHROMA:
        return get_chroma_client()
    elif storage_type == STORAGE_TYPE_PINECONE:
        return get_pinecone_client()
    elif storage_type == STORAGE_TYPE_WEAVIATE:
        raise NotImplementedError("Weaviate storage backend not yet implemented")
    else:
        raise ValueError(f"Unsupported storage type: {storage_type}")


def setup_storage():
    folders = ["raw_uploads", "uploads", "vector_db", "markdown_cache"]
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
    storage_type = get_storage_type()
    
    if storage_type == STORAGE_TYPE_CHROMA:
        from llama_index.vector_stores.chroma import ChromaVectorStore  # pyright: ignore
        db = get_storage_client()
        chroma_collection = db.get_or_create_collection(collection_name)
        return ChromaVectorStore(chroma_collection=chroma_collection)
    
    elif storage_type == STORAGE_TYPE_PINECONE:
        from llama_index.vector_stores.pinecone import PineconeVectorStore  # pyright: ignore
        
        index_name = PINECONE_INDEX_NAME or collection_name
        
        pc = get_storage_client()
        
        expected_dimension = EMBEDDING_MODEL_DIMENSION
        if PINECONE_DIMENSION != expected_dimension:
            raise ValueError(
                f"Pinecone dimension mismatch: PINECONE_DIMENSION={PINECONE_DIMENSION} "
                f"does not match EMBEDDING_MODEL_DIMENSION={expected_dimension}. "
                f"They must be equal."
            )
        
        from app.core.data import OPENAI_EMBEDDING_MODEL_DIMENSIONS
        model_dimension = OPENAI_EMBEDDING_MODEL_DIMENSIONS.get(EMBEDDING_MODEL)
        if model_dimension and expected_dimension != model_dimension:
            raise ValueError(
                f"Invalid dimension {expected_dimension} for embedding model '{EMBEDDING_MODEL}'. "
                f"Expected dimension: {model_dimension}. "
                f"Set PINECONE_DIMENSION to {model_dimension}."
            )
        
        existing_indexes = [index.name for index in pc.list_indexes()]
        
        if index_name not in existing_indexes:
            logger.info(f"Pinecone index '{index_name}' not found. Creating new index...")
            dimension = expected_dimension
            metric = PINECONE_METRIC
            cloud = PINECONE_CLOUD
            region = PINECONE_REGION
            
            from pinecone import ServerlessSpec
            
            pc.create_index(
                name=index_name,
                dimension=dimension,
                metric=metric,
                spec=ServerlessSpec(cloud=cloud, region=region)
            )
            logger.info(f"Created Pinecone index '{index_name}' with dimension {dimension} in {cloud}/{region}")
        else:
            index_info = pc.describe_index(index_name)
            existing_dimension = index_info.dimension
            if existing_dimension != expected_dimension:
                raise ValueError(
                    f"Pinecone index '{index_name}' dimension mismatch: existing dimension={existing_dimension} "
                    f"does not match embedding model '{EMBEDDING_MODEL}' dimension={expected_dimension}. "
                    f"Please recreate the index with dimension={expected_dimension} or use a different embedding model."
                )
        
        index = pc.Index(index_name)
        
        return PineconeVectorStore(pinecone_index=index)
    
    else:
        raise ValueError(f"Unsupported storage type: {storage_type}")


def get_storage_context(vector_store):
    return StorageContext.from_defaults(vector_store=vector_store)
