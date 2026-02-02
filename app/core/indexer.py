from llama_index.core import VectorStoreIndex
from app.core.storage import get_vector_store, get_storage_context

async def index_documents(documents):
    vector_store = get_vector_store()
    storage_context = get_storage_context(vector_store)
    
    return VectorStoreIndex.from_documents(
        documents, 
        storage_context=storage_context
    )