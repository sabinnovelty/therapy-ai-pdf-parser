"""
Storage backend configuration and factory.

This module determines which storage backend to use based on configuration.
Currently supports ChromaDB, but can be extended to support other backends.
"""
import os
import chromadb
from pathlib import Path
from typing import Optional
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Storage directory configuration
# Defaults to ./storage if not specified via environment variable
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "./storage"))

# Storage backend types
STORAGE_TYPE_CHROMA = "chroma"
STORAGE_TYPE_PINECONE = "pinecone"
STORAGE_TYPE_WEAVIATE = "weaviate"

def get_storage_type() -> str:
    """
    Determine which storage backend to use based on environment configuration.
    
    Returns:
        Storage backend type (defaults to "chroma")
    """
    storage_type = os.getenv("STORAGE_TYPE", STORAGE_TYPE_CHROMA).lower()
    
    valid_types = [STORAGE_TYPE_CHROMA, STORAGE_TYPE_PINECONE, STORAGE_TYPE_WEAVIATE]
    if storage_type not in valid_types:
        logger.warning(
            f"Invalid STORAGE_TYPE '{storage_type}', defaulting to '{STORAGE_TYPE_CHROMA}'"
        )
        storage_type = STORAGE_TYPE_CHROMA
    
    return storage_type

def get_chroma_client(path: Optional[Path] = None) -> chromadb.PersistentClient:
    """
    Get or create a ChromaDB persistent client.
    
    Args:
        path: Optional path to the vector database. If not provided, uses STORAGE_DIR/vector_db
        
    Returns:
        ChromaDB PersistentClient instance
    """
    if path is None:
        path = STORAGE_DIR / "vector_db"
    
    db_path = str(path)
    logger.debug(f"Initializing ChromaDB client at: {db_path}")
    
    return chromadb.PersistentClient(path=db_path)

def get_storage_client():
    """
    Factory function to get the appropriate storage client based on configuration.
    
    Returns:
        Storage client instance (currently ChromaDB PersistentClient)
        
    Raises:
        ValueError: If storage type is not supported
    """
    storage_type = get_storage_type()
    
    if storage_type == STORAGE_TYPE_CHROMA:
        return get_chroma_client()
    elif storage_type == STORAGE_TYPE_PINECONE:
        # Future implementation for Pinecone
        raise NotImplementedError("Pinecone storage backend not yet implemented")
    elif storage_type == STORAGE_TYPE_WEAVIATE:
        # Future implementation for Weaviate
        raise NotImplementedError("Weaviate storage backend not yet implemented")
    else:
        raise ValueError(f"Unsupported storage type: {storage_type}")
