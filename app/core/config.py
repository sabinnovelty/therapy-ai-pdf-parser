import os
from llama_index.core import Settings
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from app.utils.logger import get_logger

logger = get_logger(__name__)

def validate_rag_environment() -> None:
    """
    Validate that all required environment variables for RAG are set.
    
    Raises:
        ValueError: If any required environment variable is missing
    """
    required_vars = {
        "OPENAI_API_KEY": "OpenAI API key (for LLM and embeddings)"
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
    openai_api_key = os.getenv("OPENAI_API_KEY")
    
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY must be set")
    
    # Use OpenAI GPT-4o-mini for cost-effective RAG queries
    Settings.llm = OpenAI(
        model="gpt-4o-mini",
        api_key=openai_api_key,
        temperature=0.1
    )
    
    # Use OpenAI embeddings (text-embedding-3-small is cost-effective)
    Settings.embed_model = OpenAIEmbedding(
        model="text-embedding-3-small",
        api_key=openai_api_key
    )
    
    # Standard chunking is too basic; using larger chunks for healthcare context
    Settings.chunk_size = 1024
    Settings.chunk_overlap = 100
    
    logger.info("RAG settings configured successfully with OpenAI")
    