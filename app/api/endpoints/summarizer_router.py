from fastapi import APIRouter, HTTPException, status
from app.schemas.summarization_schema import (
    SummarizationRequest,
    SummarizationResponse,
    SummarizationResponseWrapper,
    ErrorResponse,
)
from app.services.summarization_service import SummarizationService

router = APIRouter()


@router.post(
    "/summarize",
    response_model=SummarizationResponseWrapper,
    responses={500: {"model": ErrorResponse}},
    summary="Summarize Case Notes",
)

async def summarize_notes(request: SummarizationRequest) -> SummarizationResponseWrapper:
    """
    Summarize case notes using AI.

    **Request Parameters:**
    - **notes**: List of case notes to summarize
    - **patientName**: Name of the patient
    - **currentCaseStatus**: Current status of the case
    - **caseId**: Unique identifier for the case (not returned in response)
    - **assignedTo**: Assigned care provider (not returned in response)

    **Response:**
    - **success**: Boolean indicating if the summarization was successful
    - **summary**: The generated summary text

    Note: The response does not include caseId, assignedTo, onBehalfOf, or summarizationType.
    """

    try:
        summary = await SummarizationService.summarize(request)
        return SummarizationResponseWrapper(
            data=SummarizationResponse(
                success=True,
                summary=summary
            )
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
