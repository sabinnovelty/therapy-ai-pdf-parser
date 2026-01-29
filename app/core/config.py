import os
from llama_index.core import Settings
from llama_index.llms.gemini import Gemini
from llama_index.embeddings.voyageai import VoyageEmbedding
from app.utils.logger import get_logger

logger = get_logger(__name__)

def validate_rag_environment() -> None:
    """
    Validate that all required environment variables for RAG are set.
    
    Raises:
        ValueError: If any required environment variable is missing
    """
    required_vars = {
        "LLAMA_CLOUD_API_KEY": "LlamaParse API key",
        "GEMINI_API_KEY": "Gemini LLM API key",
        "VOYAGE_API_KEY": "VoyageAI embeddings API key"
    }
    
    missing_vars = []
    for var_name, description in required_vars.items():
        if not os.getenv(var_name):
            missing_vars.append(f"{var_name} ({description})")
    
    if missing_vars:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )
    
    logger.info("All required RAG environment variables are set")

def configure_rag_settings() -> None:
    """Global configuration for the RAG engine."""
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    voyage_api_key = os.getenv("VOYAGE_API_KEY")
    
    if not gemini_api_key or not voyage_api_key:
        raise ValueError("GEMINI_API_KEY and VOYAGE_API_KEY must be set")
    
    Settings.llm = Gemini(
        model_name="models/gemini-1.5-pro", 
        api_key=gemini_api_key,
        temperature=0.1
    )
    Settings.embed_model = VoyageEmbedding(
        model_name="voyage-medical-2", 
        voyage_api_key=voyage_api_key
    )
    # Standard chunking is too basic; using larger chunks for healthcare context
    Settings.chunk_size = 1024
    Settings.chunk_overlap = 100
    
    logger.info("RAG settings configured successfully")
    