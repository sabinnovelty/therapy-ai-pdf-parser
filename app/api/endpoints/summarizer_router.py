from fastapi import APIRouter, HTTPException, status
from app.schemas.summarization_schema import (
    SummarizationRequest,
    SummarizationResponse,
    ErrorResponse,
)
from app.services.summarization_service import SummarizationService

router = APIRouter()


@router.post(
    "/summarize",
    response_model=SummarizationResponse,
    responses={500: {"model": ErrorResponse}},
    summary="Summarize Case Notes",
)

async def summarize_notes(request: SummarizationRequest) -> SummarizationResponse:
    """
    Summarize case notes using AI.

    - **caseId**: Unique identifier for the case
    - **notes**: List of case notes to summarize
    - **patientName**: Name of the patient
    - **assignedTo**: Assigned care provider
    - **currentCaseStatus**: Current status of the case
    - **onBehalfOf**: Role of the requesting user
    - **summarizationType**: Type of summarization (full or unread)
    """

    try:
        summary = await SummarizationService.summarize(request)
        return SummarizationResponse(
            success=True,
            caseId=request.caseId,
            summary=summary
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
