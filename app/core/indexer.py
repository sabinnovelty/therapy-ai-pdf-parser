# app/services/indexer.py
from llama_index.core import VectorStoreIndex
from app.services.storage_service import get_vector_store, get_storage_context

async def index_documents(documents):
    vector_store = get_vector_store()
    storage_context = get_storage_context(vector_store)
    
    # This creates the embeddings and saves them to disk
    return VectorStoreIndex.from_documents(
        documents, 
        storage_context=storage_context
    )