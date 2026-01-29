from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException, status
from typing import Annotated
from app.services.ingestion_service import ingest_document_functional
from app.services.advocacy_service import query_advocacy_engine
from app.services.storage_service import save_upload
from app.schemas.rag_schema import RAGResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/advocacy", tags=["Advocacy"])

async def ingest_with_error_handling(file_path: str, metadata: dict) -> None:
    """Wrapper function for background task with error handling."""
    try:
        await ingest_document_functional(file_path, metadata)
    except Exception as e:
        logger.error(
            "Background task failed",
            file_path=file_path,
            metadata=metadata,
            error=str(e),
            exc_info=True
        )

@router.post(
    "/admin/upload",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload and index document",
    description="Upload a document for indexing into the RAG system. Processing happens in background."
)
async def admin_upload(
    background_tasks: BackgroundTasks,
    tenant_id: Annotated[str, Form(..., description="Tenant identifier")],
    doc_type: Annotated[str, Form(..., description="Document type: policy, plan, regulation, or rule")],
    plan_id: Annotated[str, Form(default="GLOBAL", description="Plan identifier, defaults to GLOBAL")],
    file: Annotated[UploadFile, File(..., description="PDF file to upload")]
):
    """Upload a document for indexing."""
    try:
        logger.info(
            "Document upload request",
            tenant_id=tenant_id,
            doc_type=doc_type,
            plan_id=plan_id,
            filename=file.filename
        )
        
        # 1. Save File to local storage
        file_path = await save_upload(file, tenant_id)
        
        # 2. Metadata for the Vector DB
        metadata = {
            "tenant_id": tenant_id,
            "doc_type": doc_type,
            "plan_id": plan_id
        }
        
        # 3. Offload heavy PDF Parsing/Indexing to background with error handling
        background_tasks.add_task(ingest_with_error_handling, file_path, metadata)
        
        return {
            "message": f"Document '{file.filename}' is being indexed for tenant {tenant_id}",
            "status": "processing"
        }
    except Exception as e:
        logger.error(
            "Document upload failed",
            tenant_id=tenant_id,
            filename=file.filename,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}"
        )

@router.post(
    "/patient/chat",
    response_model=RAGResponse,
    status_code=status.HTTP_200_OK,
    summary="Query advocacy engine",
    description="Query the RAG system for healthcare advocacy information."
)
async def chat(
    tenant_id: Annotated[str, Form(..., description="Tenant identifier")],
    plan_id: Annotated[str, Form(..., description="Plan identifier")],
    query: Annotated[str, Form(..., description="User query")]
):
    """Query the advocacy engine."""
    try:
        logger.info(
            "Query request",
            tenant_id=tenant_id,
            plan_id=plan_id,
            query_length=len(query)
        )
        
        result = await query_advocacy_engine(query, tenant_id, plan_id)
        
        logger.info(
            "Query completed",
            tenant_id=tenant_id,
            plan_id=plan_id,
            sources_count=len(result.get("sources", []))
        )
        
        return RAGResponse(**result)
    except Exception as e:
        logger.error(
            "Query failed",
            tenant_id=tenant_id,
            plan_id=plan_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {str(e)}"
        )