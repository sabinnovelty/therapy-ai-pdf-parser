# app/api/endpoints/summarizer_router.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.schemas.summarization_schema import SummarizationRequest
from app.services.summarization_service import SummarizationService

router = APIRouter(prefix="/api/artificial-intelligence")


@router.post("/v2/summarize")
async def summarize(request: SummarizationRequest):
    try:
        summary = await SummarizationService.summarize(request)
        return JSONResponse(content={"summary": summary})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during summarizing the documents: {str(e)}")
