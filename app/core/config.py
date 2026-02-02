from llama_index.core import Settings
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from app.core.data import OPENAI_API_KEY, LLAMA_API_KEY, DOCUMENT_CHUNK_SIZE, DOCUMENT_CHUNK_OVERLAP, PINECONE_DIMENSION, EMBEDDING_MODEL_DIMENSION
from app.utils.logger import get_logger

logger = get_logger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"

def validate_rag_environment() -> None:
    required_vars = {
        "OPENAI_API_KEY": ("OpenAI API key (for LLM and embeddings)", OPENAI_API_KEY),
        "LLAMA_API_KEY": ("LlamaParse API key (for PDF document parsing)", LLAMA_API_KEY)
    }
    
    missing_vars = []
    for var_name, (description, value) in required_vars.items():
        if not value:
            missing_vars.append(f"{var_name} ({description})")
    
    if missing_vars:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )
    
    logger.info("All required RAG environment variables are set")

def configure_rag_settings() -> None:
    from app.core.data import OPENAI_EMBEDDING_MODEL_DIMENSIONS
    
    openai_api_key = OPENAI_API_KEY
    
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY must be set")
    
    Settings.llm = OpenAI(
        model="gpt-4o-mini",
        api_key=openai_api_key,
        temperature=0.1
    )
    
    expected_dimension = EMBEDDING_MODEL_DIMENSION
    model_dimension = OPENAI_EMBEDDING_MODEL_DIMENSIONS.get(EMBEDDING_MODEL)
    
    if model_dimension and expected_dimension != model_dimension:
        raise ValueError(
            f"Invalid dimension {expected_dimension} for embedding model '{EMBEDDING_MODEL}'. "
            f"Expected dimension: {model_dimension}. "
            f"Set PINECONE_DIMENSION to {model_dimension}."
        )
    
    if PINECONE_DIMENSION != expected_dimension:
        raise ValueError(
            f"Pinecone dimension mismatch: PINECONE_DIMENSION={PINECONE_DIMENSION} "
            f"does not match EMBEDDING_MODEL_DIMENSION={expected_dimension}. "
            f"They must be equal."
        )
    
    Settings.embed_model = OpenAIEmbedding(
        model=EMBEDDING_MODEL,
        api_key=openai_api_key,
        dimensions=expected_dimension
    )
    
    Settings.chunk_size = DOCUMENT_CHUNK_SIZE
    Settings.chunk_overlap = DOCUMENT_CHUNK_OVERLAP
    
    logger.info(f"RAG settings configured successfully with OpenAI (embedding model: {EMBEDDING_MODEL}, dimension: {expected_dimension})")
    