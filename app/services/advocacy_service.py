from typing import Dict, List
import re
from llama_index.core import VectorStoreIndex
from llama_index.core.vector_stores.types import MetadataFilters, ExactMatchFilter
from app.core.storage import get_storage_client, get_storage_type, STORAGE_TYPE_CHROMA, STORAGE_TYPE_PINECONE, get_vector_store
from app.core.data import DEFAULT_COLLECTION_NAME, PINECONE_INDEX_NAME, PINECONE_DIMENSION
from app.prompts.advocacy_prompts import ADVOCACY_SYSTEM_PROMPT
from app.utils.logger import get_logger

logger = get_logger(__name__)


def limit_to_first_n_sentences(text: str, n: int = 10) -> str:
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
    try:
        storage_type = get_storage_type()
        collection_name = DEFAULT_COLLECTION_NAME
        
        if storage_type == STORAGE_TYPE_CHROMA:
            db = get_storage_client()
            collection = db.get_or_create_collection(collection_name)
            count = collection.count()
            return count
        
        elif storage_type == STORAGE_TYPE_PINECONE:
            pc = get_storage_client()
            index_name = PINECONE_INDEX_NAME or collection_name
            index = pc.Index(index_name)
            
            # Get index stats
            stats = index.describe_index_stats()
            # Pinecone returns total_vector_count in stats
            count = stats.get("total_vector_count", 0)
            return count
        
        else:
            logger.error(f"Unsupported storage type: {storage_type}")
            return 0
            
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
        storage_type = get_storage_type()
        collection_name = DEFAULT_COLLECTION_NAME
        
        if storage_type == STORAGE_TYPE_CHROMA:
            # Connect directly to storage backend (determined by core/storage.py)
            db = get_storage_client()
            collection = db.get_or_create_collection(collection_name)
            
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
        
        elif storage_type == STORAGE_TYPE_PINECONE:
            pc = get_storage_client()
            index_name = PINECONE_INDEX_NAME or collection_name
            index = pc.Index(index_name)
            
            # Get index stats
            stats = index.describe_index_stats()
            count = stats.get("total_vector_count", 0)
            logger.info(f"Total entries in database: {count}")
            
            # Query Pinecone to get sample entries
            # Note: Pinecone doesn't have a direct "get all" API, so we use query with a dummy vector
            # For checking contents, we'll use fetch with known IDs or query with metadata filter
            # Since we don't know IDs, we'll query with a zero vector (not ideal but works for inspection)
            try:
                dimension = PINECONE_DIMENSION
                zero_vector = [0.0] * dimension
                
                # Query with top_k to get sample entries
                query_results = index.query(
                    vector=zero_vector,
                    top_k=min(limit, count),
                    include_metadata=True
                )
                
                entries = []
                if query_results and query_results.get('matches'):
                    for match in query_results['matches']:
                        entry_id = match.get('id', '')
                        metadata = match.get('metadata', {})
                        # Pinecone doesn't store text directly, it's in metadata or we need to reconstruct
                        text = metadata.get('text', metadata.get('content', ''))
                        entry = {
                            "id": entry_id,
                            "text": text[:200] + "..." if text and len(text) > 200 else text,
                            "text_length": len(text) if text else 0,
                            "metadata": metadata
                        }
                        entries.append(entry)
                
                logger.info(f"Retrieved {len(entries)} entries from database (total: {count})")
                return entries
                
            except Exception as query_error:
                logger.warning(f"Could not query Pinecone for sample entries: {query_error}")
                # Return empty list with count info
                return [{"id": "N/A", "text": f"Total entries: {count}", "text_length": 0, "metadata": {}}]
        
        else:
            raise ValueError(f"Unsupported storage type: {storage_type}")
        
    except Exception as e:
        logger.error(f"Error checking database contents: {e}", exc_info=True)
        raise

async def query_advocacy_engine(query: str, tenant_id: str, plan_id: str, category: str = "advocacy") -> Dict[str, List[str]]:
    try:
        await logger.info(
            "Querying advocacy engine",
            tenant_id=tenant_id,
            plan_id=plan_id,
            category=category,
            query_length=len(query)
        )
        
        vector_store = get_vector_store()
        index = VectorStoreIndex.from_vector_store(vector_store)
        
        filters = MetadataFilters(filters=[
            ExactMatchFilter(key="tenant_id", value=tenant_id),
            ExactMatchFilter(key="category", value=category),
        ])

        await logger.info(f"Filters applied: tenant_id={tenant_id}, category={category}")
        
        query_engine = index.as_query_engine(
            filters=filters,
            text_qa_template=ADVOCACY_SYSTEM_PROMPT,
            similarity_top_k=5
        )

        await logger.info(f"Query engine initialized")
        
        response = await query_engine.aquery(query)

        await logger.info(f"Query response received")
        
        filtered_sources = []
        total_source_nodes = len(response.source_nodes) if hasattr(response, 'source_nodes') else 0
        
        for node in response.source_nodes:
            source_file = node.metadata.get("source_file")
            if source_file:
                filtered_sources.append(source_file)
        
        sources = list(set(filtered_sources))
        
        await logger.info(
            "Source nodes analysis",
            total_nodes=total_source_nodes,
            filtered_sources_count=len(sources),
            tenant_id=tenant_id,
            plan_id=plan_id,
            category=category
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
    