from pydantic import BaseModel, Field
from typing import List, Optional

class AdminIngestRequest(BaseModel):
    tenant_id: str
    doc_type: str = Field(..., description="policy, plan, regulation, or rule")
    category: Optional[str] = "advocacy"

class PatientQueryRequest(BaseModel):
    tenant_id: str
    plan_id: Optional[str] = "GLOBAL"
    query: str

class RAGResponse(BaseModel):
    answer: str
    sources: List[str]

class DocumentInfo(BaseModel):
    tenant_id: str
    filename: str
    file_path: str
    file_size: int
    uploaded_at: str

class DocumentListResponse(BaseModel):
    total_documents: int
    documents: List[DocumentInfo]