from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from typing import Annotated
from app.services.ingestion_service import ingest_document_functional
from app.services.advocacy_service import query_advocacy_engine, check_database_contents, get_database_count
from app.services.storage_service import save_upload
from app.schemas.rag_schema import RAGResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v2/ai-services", tags=["Advocacy"])

@router.post(
    "/admin/upload",
    status_code=status.HTTP_200_OK,
    summary="Upload and index document",
    description="Upload a document for indexing into the RAG system. Returns success status and database size after indexing completes."
)
async def admin_upload(
    tenant_id: Annotated[str, Form(..., description="Tenant identifier")],
    doc_type: Annotated[str, Form(..., description="Document type: policy, plan, regulation, or rule")],
    file: Annotated[UploadFile, File(..., description="PDF file to upload")],
    plan_id: Annotated[str, Form(description="Plan identifier, defaults to GLOBAL")] = "GLOBAL"
):
    """Upload a document for indexing."""
    try:
        await logger.info(
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
        
        # 3. Get database count before ingestion
        count_before = get_database_count()
        
        # 4. Process ingestion (wait for completion to get updated count)
        try:
            count_after = await ingest_document_functional(file_path, metadata)
            
            return {
                "success": True,
                "message": f"Document '{file.filename}' has been successfully indexed for tenant {tenant_id}",
                "database_size": count_after,
                "chunks_added": count_after - count_before
            }
        except Exception as e:
            # If ingestion fails, still return current database size
            current_count = get_database_count()
            await logger.error(
                "Document ingestion failed in upload endpoint",
                tenant_id=tenant_id,
                filename=file.filename,
                error=str(e),
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to index document: {str(e)}"
            )
    except Exception as e:
        await logger.error(
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
        await logger.info(
            "Query request",
            tenant_id=tenant_id,
            plan_id=plan_id,
            query_length=len(query)
        )
        
        result = await query_advocacy_engine(query, tenant_id, plan_id)
        
        await logger.info(
            "Query completed",
            tenant_id=tenant_id,
            plan_id=plan_id,
            sources_count=len(result.get("sources", [])),
            answer_length=len(result.get("answer", "")),
            result_keys=list(result.keys()),
            answer_preview=result.get("answer", "")[:100] if result.get("answer") else "EMPTY"
        )
        
        # Ensure answer is never empty - provide fallback
        if not result.get("answer") or not result.get("answer").strip():
            result["answer"] = "I cannot find this information in the documents provided by your administrator."
            await logger.warning("Answer was empty, using fallback message")
        
        return RAGResponse(**result)
    except Exception as e:
        await logger.error(
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

@router.get(
    "/admin/check-db",
    status_code=status.HTTP_200_OK,
    summary="Check database contents",
    description="Simple endpoint to check what's stored in the embedded database (first 20 entries)"
)
async def check_db(limit: int = 20):
    """Check what's stored in the database."""
    try:
        entries = check_database_contents(limit=limit)
        return {
            "total_entries": len(entries),
            "entries": entries
        }
    except Exception as e:
        await logger.error(
            "Database check failed",
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check database: {str(e)}"
        )