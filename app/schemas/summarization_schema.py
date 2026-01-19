from pydantic import BaseModel
from typing import List, Optional


class CreatedBy(BaseModel):
    name: str


class Note(BaseModel):
    note: str
    createdBy: CreatedBy


class SummarizationRequest(BaseModel):
    caseId: str
    notes: List[Note]
    patientName: str
    assignedTo: Optional[str] = None
    currentCaseStatus: Optional[str] = None
    onBehalfOf: Optional[str] = None
    summarizationType: Optional[str] = None  # "full" or "unread"


class SummarizationResponse(BaseModel):
    success: bool
    summary: str


class SummarizationResponseWrapper(BaseModel):
    data: SummarizationResponse


class ErrorResponse(BaseModel):
    detail: str
