import os
from typing import Dict
from llama_index.core import VectorStoreIndex, Settings
from llama_index.core.node_parser import SemanticSplitterNodeParser
from app.core.parser import parse_pdf_to_docs
from app.core.storage import get_storage_client, get_storage_type, STORAGE_TYPE_CHROMA, STORAGE_TYPE_PINECONE, get_vector_store, get_storage_context
from app.core.data import DEFAULT_CATEGORY, DEFAULT_COLLECTION_NAME, PINECONE_INDEX_NAME
from app.utils.logger import get_logger

logger = get_logger(__name__)

async def ingest_document_functional(file_path: str, metadata: Dict[str, str]) -> int:
    try:
        await logger.info(
            "Starting document ingestion",
            file_path=file_path,
            tenant_id=metadata.get("tenant_id"),
            doc_type=metadata.get("doc_type"),
            category=metadata.get("category")
        )
        
        documents = await parse_pdf_to_docs(file_path, metadata.get("category", DEFAULT_CATEGORY), metadata.get("tenant_id"))
        
        await logger.info(f"Parsed {len(documents)} document chunks", file_path=file_path)
        
        # Metadata tagging for filtering
        for doc in documents:
            doc.metadata.update(metadata)
            doc.metadata["source_file"] = os.path.basename(file_path)

        vector_store = get_vector_store()
        
        index = VectorStoreIndex.from_vector_store(vector_store)
        
        # Get count before insertion (storage-type agnostic)
        storage_type = get_storage_type()
        collection_name = DEFAULT_COLLECTION_NAME
        
        if storage_type == STORAGE_TYPE_CHROMA:
            db = get_storage_client()
            collection = db.get_or_create_collection(collection_name)
            count_before = collection.count()
        elif storage_type == STORAGE_TYPE_PINECONE:
            pc = get_storage_client()
            index_name = PINECONE_INDEX_NAME
            pinecone_index = pc.Index(index_name)
            stats = pinecone_index.describe_index_stats()
            count_before = stats.get("total_vector_count", 0)
        else:
            count_before = 0
        
        node_parser = SemanticSplitterNodeParser(
            embed_model=Settings.embed_model,  # Use the configured embedding model
            buffer_size=1,  # Number of sentences to include around each semantic boundary
        )
        nodes = node_parser.get_nodes_from_documents(documents)
        
        # Insert nodes into the existing index
        # This will generate embeddings for each node
        index.insert_nodes(nodes)
        
        # Get count after insertion (storage-type agnostic)
        if storage_type == STORAGE_TYPE_CHROMA:
            count_after = collection.count()
        elif storage_type == STORAGE_TYPE_PINECONE:
            stats = pinecone_index.describe_index_stats()
            count_after = stats.get("total_vector_count", 0)
        else:
            count_after = count_before + len(nodes)
        
        chunks_added = count_after - count_before
        
        await logger.info(
            f"Inserted {len(nodes)} nodes into index (from {len(documents)} documents). "
            f"Database size: {count_before} -> {count_after} (added {chunks_added} chunks)"
        )
        
        await logger.info(
            "Document ingestion completed successfully",
            file_path=file_path,
            tenant_id=metadata.get("tenant_id"),
            chunks_indexed=len(nodes),
            database_size=count_after
        )
        
        return count_after
    except Exception as e:
        await logger.error(
            "Document ingestion failed",
            file_path=file_path,
            tenant_id=metadata.get("tenant_id"),
            error=str(e),
            exc_info=True
        )
        raise
