import os
from typing import Dict
from llama_index.core import VectorStoreIndex, Settings
from llama_index.core.node_parser import SentenceSplitter
from app.core.parser import parse_pdf_to_docs
from app.core.storage import get_storage_client
from app.services.storage_service import get_vector_store, get_storage_context
from app.utils.logger import get_logger

logger = get_logger(__name__)

async def ingest_document_functional(file_path: str, metadata: Dict[str, str]) -> int:
    """
    Ingest a document into the vector database with metadata tagging.
    
    Args:
        file_path: Path to the PDF file to ingest
        metadata: Dictionary containing tenant_id, doc_type, and plan_id
        
    Raises:
        Exception: If document parsing or indexing fails
    """
    try:
        await logger.info(
            "Starting document ingestion",
            file_path=file_path,
            tenant_id=metadata.get("tenant_id"),
            doc_type=metadata.get("doc_type"),
            plan_id=metadata.get("plan_id")
        )
        
        # PDF Parsing Step - using open-source parser
        plan_id = metadata.get("plan_id", "GLOBAL")
        documents = await parse_pdf_to_docs(file_path, plan_id)
        
        await logger.info(f"Parsed {len(documents)} document chunks", file_path=file_path)
        
        # Metadata tagging for filtering
        for doc in documents:
            doc.metadata.update(metadata)
            doc.metadata["source_file"] = os.path.basename(file_path)

        # Ingestion into Vector DB - use storage_service function for consistency
        vector_store = get_vector_store()  # Uses consistent "healthcare_index" collection
        
        # Load existing index or create new one
        # from_vector_store will load existing index if it exists, otherwise creates new one
        index = VectorStoreIndex.from_vector_store(vector_store)
        
        # Get count before insertion
        db = get_storage_client()
        collection = db.get_or_create_collection("healthcare_index")
        count_before = collection.count()
        
        # Convert documents to nodes first, then insert nodes
        # This ensures proper chunking based on Settings.chunk_size and Settings.chunk_overlap
        node_parser = SentenceSplitter(
            chunk_size=Settings.chunk_size,
            chunk_overlap=Settings.chunk_overlap
        )
        nodes = node_parser.get_nodes_from_documents(documents)
        
        # Insert nodes into the existing index
        # This will generate embeddings for each node
        index.insert_nodes(nodes)
        
        # Get count after insertion
        count_after = collection.count()
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
