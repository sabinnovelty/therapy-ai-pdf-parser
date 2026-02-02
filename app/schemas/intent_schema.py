from enum import Enum
from typing import Annotated
from pydantic import BaseModel, Field

class UserIntent(str, Enum):
    """
    Enumeration of possible user intents for the healthcare assistant.
    """
    PLAN_SPECIFIC = "plan_specific"   # Queries regarding insurance docs/RAG
    GENERAL_HEALTH = "general_health" # LLM internal medical knowledge
    GENERAL_WEB = "general_web"       # External search required (PubMed/Web)
    GREETING = "greeting"             # Casual conversation/Intro
    OTHER = "other"                   # Off-topic or out-of-scope queries

class IntentRouting(BaseModel):
    intent: UserIntent = Field(
        ..., 
        description="The classified category of the user's query."
    )
    
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        ..., 
        description="Confidence score of the classification, between 0 and 1."
    )
    
    reasoning: str = Field(
        ..., 
        description="A brief explanation of why this intent was selected."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "intent": "plan_specific",
                "confidence": 0.92,
                "reasoning": "User mentioned 'deductible' and 'copay', which are insurance-specific terms."
            }
        }