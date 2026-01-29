from typing import Dict, List
import re
from llama_index.core import VectorStoreIndex
from llama_index.core.vector_stores.types import MetadataFilters, ExactMatchFilter
from app.core.storage import get_storage_client
from app.services.storage_service import get_vector_store
from app.prompts.advocacy_prompts import ADVOCACY_SYSTEM_PROMPT
from app.utils.logger import get_logger

logger = get_logger(__name__)


def limit_to_first_n_sentences(text: str, n: int = 10) -> str:
    """
    Limit text to the first N sentences.
    
    Args:
        text: Input text to limit
        n: Number of sentences to keep (default: 10)
        
    Returns:
        Text limited to first N sentences, or original text if fewer sentences exist
    """
    if not text or not text.strip():
        return text
    
    # Split text into sentences using regex (handles periods, exclamation marks, question marks)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    # Filter out empty sentences
    sentences = [s.strip() for s in sentences if s.strip()]
    
    # Take only first N sentences
    if len(sentences) > n:
        return ' '.join(sentences[:n])
    
    return text

def get_database_count() -> int:
    """
    Get the total number of entries in the vector database.
    
    Returns:
        Total count of entries in the database
    """
    try:
        db = get_storage_client()
        collection = db.get_or_create_collection("healthcare_index")
        count = collection.count()
        return count
    except Exception as e:
        logger.error(f"Error getting database count: {e}", exc_info=True)
        return 0

def check_database_contents(limit: int = 20) -> List[Dict]:
    """
    Simple function to check what's stored in the embedded database.
    Returns the first N entries with their text and metadata.
    
    Args:
        limit: Number of entries to return (default: 20)
        
    Returns:
        List of dictionaries containing id, text, and metadata for each entry
    """
    try:
        # Connect directly to storage backend (determined by core/storage.py)
        db = get_storage_client()
        collection = db.get_or_create_collection("healthcare_index")
        
        # Get count first
        count = collection.count()
        logger.info(f"Total entries in database: {count}")
        
        # Get all entries (or up to limit)
        results = collection.get(limit=limit)
        
        # Format results
        entries = []
        if results and results.get('ids'):
            for i, entry_id in enumerate(results['ids']):
                text = results.get('documents', [None])[i] if results.get('documents') else None
                metadata = results.get('metadatas', [{}])[i] if results.get('metadatas') else {}
                entry = {
                    "id": entry_id,
                    "text": text[:200] + "..." if text and len(text) > 200 else text,  # Truncate long text
                    "text_length": len(text) if text else 0,
                    "metadata": metadata
                }
                entries.append(entry)
        
        logger.info(f"Retrieved {len(entries)} entries from database (total: {count})")
        return entries
        
    except Exception as e:
        logger.error(f"Error checking database contents: {e}", exc_info=True)
        raise

async def query_advocacy_engine(query: str, tenant_id: str, plan_id: str) -> Dict[str, List[str]]:
    """
    Query the advocacy engine with multi-tenancy filtering.
    
    Filters documents for the specific tenant AND (Global rules OR the user's specific plan).
    
    Args:
        query: User query string
        tenant_id: Tenant identifier
        plan_id: Plan identifier (or "GLOBAL")
        
    Returns:
        Dictionary containing answer and sources
        
    Raises:
        Exception: If query execution fails
    """
    try:
        await logger.info(
            "Querying advocacy engine",
            tenant_id=tenant_id,
            plan_id=plan_id,
            query_length=len(query)
        )
        
        vector_store = get_vector_store()  # Uses consistent "healthcare_index" collection
        index = VectorStoreIndex.from_vector_store(vector_store)
        
        # MULTI-TENANCY FILTERING
        # We fetch docs for the specific tenant AND (Global rules OR the user's specific plan)
        # Note: ChromaDB doesn't support OR filters directly, so we filter results post-query
        filters_tenant = MetadataFilters(filters=[
            ExactMatchFilter(key="tenant_id", value=tenant_id),
        ])

        await logger.info(f"Filters tenant up here: {filters_tenant}")
        
        query_engine = index.as_query_engine(
            filters=filters_tenant,
            text_qa_template=ADVOCACY_SYSTEM_PROMPT,
            similarity_top_k=5
        )

        await logger.info(f"Query engine up here: {query_engine}")
        
        response = await query_engine.aquery(query)

        await logger.info(f"Response up here: {response}")
        
        # Filter source nodes to include only GLOBAL or matching plan_id
        filtered_sources = []
        total_source_nodes = len(response.source_nodes) if hasattr(response, 'source_nodes') else 0
        
        for node in response.source_nodes:
            node_plan_id = node.metadata.get("plan_id", "")
            if node_plan_id == "GLOBAL" or node_plan_id == plan_id:
                filtered_sources.append(node.metadata.get("source_file"))
        
        sources = list(set(filtered_sources))
        
        # Log source node information
        await logger.info(
            "Source nodes analysis",
            total_nodes=total_source_nodes,
            filtered_sources_count=len(sources),
            tenant_id=tenant_id,
            plan_id=plan_id
        )
        
        # Extract answer text from LlamaIndex Response object
        # According to LlamaIndex docs, Response object has a 'response' attribute containing the text
        # Try direct access first (most common case)
        try:
            answer_text = str(response.response).strip() if response.response else ""
        except AttributeError:
            # Fallback if response attribute doesn't exist
            await logger.warning("Response object does not have 'response' attribute, trying alternatives")
            try:
                answer_text = str(response).strip()
                # If str() returns object representation, it's not useful
                if answer_text.startswith('<') or 'Response' in answer_text or not answer_text:
                    answer_text = ""
            except Exception as e:
                await logger.error(f"Error extracting answer: {e}")
                answer_text = ""
        
        # Limit answer to first 10 sentences from embedding
        original_answer_length = len(answer_text) if answer_text else 0
        answer_text = limit_to_first_n_sentences(answer_text, n=10)
        if len(answer_text) < original_answer_length:
            await logger.info(
                "Answer limited to first 10 sentences",
                original_length=original_answer_length,
                limited_length=len(answer_text),
                tenant_id=tenant_id,
                plan_id=plan_id
            )
        
        # Log extraction result for debugging
        await logger.info(
            "Answer extraction",
            answer_length=len(answer_text),
            answer_preview=answer_text[:200] if answer_text else "EMPTY",
            sources_count=len(sources),
            has_response_attr=hasattr(response, 'response'),
            total_source_nodes=len(response.source_nodes) if hasattr(response, 'source_nodes') else 0
        )
        
        # Handle cases where no documents were found or LLM returned empty/generic response
        # Check for common "empty" responses from LLM when no context is available
        empty_responses = ["empty response", "empty", "no response", "i cannot", "i don't have"]
        answer_lower = answer_text.lower().strip()
        original_answer = answer_text  # Save original for logging
        
        # If no sources found OR answer indicates empty/no information
        if len(sources) == 0 or any(empty in answer_lower for empty in empty_responses) or not answer_text:
            answer_text = "I cannot find this information in the documents provided by your administrator."
            await logger.warning(
                "No relevant documents found or empty response from LLM",
                tenant_id=tenant_id,
                plan_id=plan_id,
                sources_count=len(sources),
                total_source_nodes=len(response.source_nodes) if hasattr(response, 'source_nodes') else 0,
                query=query,
                original_answer=original_answer if original_answer else "EMPTY"
            )
        
        await logger.info(
            "Query completed",
            tenant_id=tenant_id,
            plan_id=plan_id,
            sources_count=len(sources),
            answer_length=len(answer_text)
        )
        
        return {
            "answer": answer_text,
            "sources": sources
        }
    except Exception as e:
        await logger.error(
            "Query advocacy engine failed",
            tenant_id=tenant_id,
            plan_id=plan_id,
            error=str(e),
            exc_info=True
        )
        raise
    