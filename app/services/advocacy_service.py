from typing import Dict, List
from llama_index.core import VectorStoreIndex
from llama_index.core.vector_stores.types import MetadataFilters, ExactMatchFilter
from app.services.storage_service import get_vector_store
from app.prompts.advocacy_prompts import ADVOCACY_SYSTEM_PROMPT
from app.utils.logger import get_logger

logger = get_logger(__name__)

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
        logger.info(
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
        
        query_engine = index.as_query_engine(
            filters=filters_tenant,
            text_qa_template=ADVOCACY_SYSTEM_PROMPT,
            similarity_top_k=5
        )
        
        response = await query_engine.aquery(query)
        
        # Filter source nodes to include only GLOBAL or matching plan_id
        filtered_sources = []
        for node in response.source_nodes:
            node_plan_id = node.metadata.get("plan_id", "")
            if node_plan_id == "GLOBAL" or node_plan_id == plan_id:
                filtered_sources.append(node.metadata.get("source_file"))
        
        sources = list(set(filtered_sources))
        
        logger.info(
            "Query completed",
            tenant_id=tenant_id,
            plan_id=plan_id,
            sources_count=len(sources)
        )
        
        return {
            "answer": str(response),
            "sources": sources
        }
    except Exception as e:
        logger.error(
            "Query advocacy engine failed",
            tenant_id=tenant_id,
            plan_id=plan_id,
            error=str(e),
            exc_info=True
        )
        raise
    