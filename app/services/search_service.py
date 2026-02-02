from typing import Dict, List
from app.utils.logger import get_logger
from app.core.data import ADVOCATE_ASSISTANT_NAME
import asyncio
from duckduckgo_search import DDGS

logger = get_logger(__name__)


async def web_search(query: str) -> Dict[str, List[str]]:
    try:
        await logger.info(
            "Querying web search",
            query_length=len(query)
        )
        
        def _search():
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=5))
                return results
        
        results = await asyncio.to_thread(_search)
        
        if not results:
            return {
                "answer": f"I searched the web for '{query}' but didn't find relevant results. Please try rephrasing your question.",
                "sources": []
            }
        
        sources = [result.get("href", "") for result in results if result.get("href")]
        answer_parts = []
        
        for i, result in enumerate(results[:3], 1):
            title = result.get("title", "")
            body = result.get("body", "")
            if title and body:
                answer_parts.append(f"{i}. {title}: {body[:200]}...")
        
        answer = "Based on web search results:\n\n" + "\n\n".join(answer_parts)
        
        return {
            "answer": answer,
            "sources": sources
        }
    except Exception as e:
        await logger.error(
            "Web search failed",
            error=str(e),
            exc_info=True
        )
        raise


async def general_medical_search(query: str) -> Dict[str, List[str]]:
    try:
        await logger.info(
            "Querying general medical search",
            query_length=len(query)
        )
        
        medical_query = f"medical {query}" if not query.lower().startswith(("medical", "health", "treatment", "symptom", "disease", "condition", "diagnosis")) else query
        
        def _search():
            with DDGS() as ddgs:
                results = list(ddgs.text(medical_query, max_results=5))
                return results
        
        results = await asyncio.to_thread(_search)
        
        if not results:
            return {
                "answer": f"I searched for medical information about '{query}' but didn't find relevant results. Please try rephrasing your question or consult with a healthcare professional.",
                "sources": []
            }
        
        sources = [result.get("href", "") for result in results if result.get("href")]
        answer_parts = []
        
        for i, result in enumerate(results[:3], 1):
            title = result.get("title", "")
            body = result.get("body", "")
            if title and body:
                answer_parts.append(f"{i}. {title}: {body[:200]}...")
        
        answer = "Based on general medical information:\n\n" + "\n\n".join(answer_parts)
        
        return {
            "answer": answer,
            "sources": sources
        }
    except Exception as e:
        await logger.error(
            "General medical search failed",
            error=str(e),
            exc_info=True
        )
        raise


async def other_search(query: str) -> Dict[str, List[str]]:
    try:
        await logger.info(
            "Querying other search",
            query_length=len(query)
        )
        
        return {
            "answer": f"I'm {ADVOCATE_ASSISTANT_NAME}, a healthcare assistant focused on helping with your healthcare queries. I'm not able to help with topics outside of healthcare. Is there something health-related I can help you with?",
            "sources": []
        }
    except Exception as e:
        await logger.error(
            "Other search failed",
            error=str(e),
            exc_info=True
        )
        raise