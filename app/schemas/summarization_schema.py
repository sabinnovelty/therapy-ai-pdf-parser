from pydantic import BaseModel
from typing import List


class CreatedBy(BaseModel):
    name: str


class Note(BaseModel):
    note: str
    createdBy: CreatedBy


class SummarizationRequest(BaseModel):
    caseId: str
    notes: List[Note]
    patientName: str
    assignedTo: str
    currentCaseStatus: str
    onBehalfOf: str
    summarizationType: str  # "full" or "unread"


class SummarizationResponse(BaseModel):
    success: bool
    summary: str


class ErrorResponse(BaseModel):
    detail: str
