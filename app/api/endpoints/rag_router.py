import os
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Query
from typing import Annotated, Optional
from app.services.ingestion_service import ingest_document_functional
from app.services.advocacy_service import query_advocacy_engine, check_database_contents, get_database_count
from app.core.storage import save_upload
from app.services.document_service import list_uploaded_documents
from app.schemas.rag_schema import RAGResponse, DocumentListResponse, DocumentInfo
from app.utils.logger import get_logger
from app.services.query_orcehstrator_service import QueryOrchestrator

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v2/ai-services", tags=["Advocacy"])

orchestrator = QueryOrchestrator()

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
    category: Annotated[str, Form(description="Document category, defaults to advocacy")] = "advocacy"
):
    """Upload a document for indexing."""
    await logger.info(
        "Document upload request",
        tenant_id=tenant_id,
        doc_type=doc_type,
        category=category,
        filename=file.filename
    )
    
    file_path = await save_upload(file, tenant_id)
    
    metadata = {
        "tenant_id": tenant_id,
        "doc_type": doc_type,
        "category": category
    }
    
    count_before = get_database_count()
    
    try:
        count_after = await ingest_document_functional(file_path, metadata)
        
        return {
            "success": True,
            "message": f"Document '{file.filename}' has been successfully indexed for tenant {tenant_id}",
            "database_size": count_after,
            "chunks_added": count_after - count_before
        }
    except Exception as e:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                await logger.info(
                    "Deleted file from raw_uploads after failed ingestion",
                    tenant_id=tenant_id,
                    filename=file.filename,
                    file_path=file_path
                )
        except Exception as delete_error:
            await logger.error(
                "Failed to delete file from raw_uploads after ingestion failure",
                tenant_id=tenant_id,
                filename=file.filename,
                file_path=file_path,
                delete_error=str(delete_error),
                exc_info=True
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to index document: {str(e)}"
        )

@router.post(
    "/patient/chat",
    response_model=RAGResponse,
    status_code=status.HTTP_200_OK,
    summary="Query advocacy engine",
    description="Query the RAG system for healthcare advocacy information. Plan identifier will be extracted from encrypted token in future updates."
)
async def chat(
    tenant_id: Annotated[str, Form(..., description="Tenant identifier. Will be extracted from encrypted token in future updates.")],
    plan_id: Annotated[str, Form(..., description="Plan identifier. Will be extracted from encrypted token in future updates.")],
    query: Annotated[str, Form(..., description="User query")]
):
    """Query the advocacy engine."""
    await logger.info(
        "Query request",
        tenant_id=tenant_id,
        plan_id=plan_id,
        query_length=len(query)
    )
    
    result = await orchestrator.process_user_query(
        query=query,
        tenant_id=tenant_id,
        plan_id=plan_id
    )
    
    await logger.info(
        "Query completed",
        tenant_id=tenant_id,
        plan_id=plan_id,
        sources_count=len(result.get("sources", [])),
        answer_length=len(result.get("answer", "")),
        result_keys=list(result.keys()),
        answer_preview=result.get("answer", "")[:100] if result.get("answer") else "EMPTY"
    )
    
    if not result.get("answer") or not result.get("answer").strip():
        result["answer"] = "I cannot find this information in the documents provided by your administrator."
        await logger.warning("Answer was empty, using fallback message")
    
    return RAGResponse(**result)

@router.get(
    "/admin/check-db",
    status_code=status.HTTP_200_OK,
    summary="Check database contents",
    description="Simple endpoint to check what's stored in the embedded database (first 20 entries)"
)
async def check_db(limit: int = 20):
    """Check what's stored in the database."""
    entries = check_database_contents(limit=limit)
    return {
        "total_entries": len(entries),
        "entries": entries
    }

@router.get(
    "/admin/list-documents",
    response_model=DocumentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List uploaded documents",
    description="List all documents that have been uploaded to the system. Optionally filter by tenant_id."
)

async def list_documents(tenant_id: Optional[str] = Query(None, description="Optional tenant identifier to filter documents")):
    """List uploaded documents, optionally filtered by tenant_id."""
    await logger.info(
        "List documents request",
        tenant_id=tenant_id if tenant_id else "all"
    )
    
    documents = list_uploaded_documents(tenant_id=tenant_id)
    document_infos = [DocumentInfo(**doc) for doc in documents]
    
    return DocumentListResponse(
        total_documents=len(document_infos),
        documents=document_infos
    )