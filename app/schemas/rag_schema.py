from pydantic import BaseModel, Field
from typing import List, Optional

class AdminIngestRequest(BaseModel):
    tenant_id: str
    doc_type: str = Field(..., description="policy, plan, regulation, or rule")
    plan_id: Optional[str] = "GLOBAL"

class PatientQueryRequest(BaseModel):
    tenant_id: str
    plan_id: Optional[str] = "GLOBAL"
    query: str

class RAGResponse(BaseModel):
    answer: str
    sources: List[str]