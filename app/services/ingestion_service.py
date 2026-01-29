import os
from typing import Dict
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex
from app.core.parser import get_medical_parser
from app.services.storage_service import get_vector_store, get_storage_context
from app.utils.logger import get_logger

logger = get_logger(__name__)

async def ingest_document_functional(file_path: str, metadata: Dict[str, str]) -> None:
    """
    Ingest a document into the vector database with metadata tagging.
    
    Args:
        file_path: Path to the PDF file to ingest
        metadata: Dictionary containing tenant_id, doc_type, and plan_id
        
    Raises:
        Exception: If document parsing or indexing fails
    """
    try:
        logger.info(
            "Starting document ingestion",
            file_path=file_path,
            tenant_id=metadata.get("tenant_id"),
            doc_type=metadata.get("doc_type"),
            plan_id=metadata.get("plan_id")
        )
        
        # PDF Parsing Step
        parser = get_medical_parser()
        
        # Load and Parse
        documents = await SimpleDirectoryReader(
            input_files=[file_path], 
            file_extractor={".pdf": parser}
        ).aload_data()
        
        logger.info(f"Parsed {len(documents)} document chunks", file_path=file_path)
        
        # Metadata tagging for filtering
        for doc in documents:
            doc.metadata.update(metadata)
            doc.metadata["source_file"] = os.path.basename(file_path)

        # Ingestion into Vector DB - use storage_service function for consistency
        vector_store = get_vector_store()  # Uses consistent "healthcare_index" collection
        storage_context = get_storage_context(vector_store)
        VectorStoreIndex.from_documents(documents, storage_context=storage_context)
        
        logger.info(
            "Document ingestion completed successfully",
            file_path=file_path,
            tenant_id=metadata.get("tenant_id"),
            chunks_indexed=len(documents)
        )
    except Exception as e:
        logger.error(
            "Document ingestion failed",
            file_path=file_path,
            tenant_id=metadata.get("tenant_id"),
            error=str(e),
            exc_info=True
        )
        raise
