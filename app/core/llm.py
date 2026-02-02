from langchain_openai import ChatOpenAI
from app.core.data import OPENAI_API_KEY
from app.utils.logger import get_logger

logger = get_logger(__name__)

def get_chat_llm_mini(temperature: float = 0.7) -> ChatOpenAI:
    openai_api_key = OPENAI_API_KEY
    
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY must be set")
    
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=temperature,
        api_key=openai_api_key
    )
