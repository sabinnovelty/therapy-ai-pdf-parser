Yes, exactly. You have hit on a crucial software design distinction:

1. **FastAPI Router (`APIRouter`):** Handles **HTTP Traffic** (Validation, Status Codes, Request Parsing).
2. **Semantic Router (Service Layer):** Handles **Business Logic Traffic** (Deciding *intent* and routing to the right AI agent).

You should **never** put business logic (like "if query implies general health, go to Google") inside your FastAPI endpoint. That makes the code untestable and messy.

Here is your refactored architecture.

### 1. The New FastAPI Router (`app/api/routes/advocacy.py`)

*This file is now "dumb." It just receives the request and hands it off to the Orchestrator.*

```python
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from typing import Annotated
from app.services.ingestion_service import ingest_document_functional
from app.services.storage_service import save_upload
from app.services.orchestrator_service import AdvocacyOrchestrator # <--- NEW SERVICE
from app.schemas.rag_schema import RAGResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v2/ai-services", tags=["Advocacy"])

# Initialize the orchestrator
orchestrator = AdvocacyOrchestrator()

@router.post("/patient/chat", response_model=RAGResponse)
async def chat(
    tenant_id: Annotated[str, Form(...)],
    plan_id: Annotated[str, Form(...)],
    query: Annotated[str, Form(...)]
):
    """
    Intelligent Advocacy Chat Endpoint.
    Routes queries to Plan Agent, General Health Agent, or Action Agent based on intent.
    """
    try:
        await logger.info(f"Received query for tenant {tenant_id}: {query[:50]}...")
        
        # DELEGATE TO ORCHESTRATOR
        # The API layer doesn't care HOW the answer is found, just that it returns.
        result = await orchestrator.process_user_query(query, tenant_id, plan_id)
        
        return RAGResponse(**result)

    except Exception as e:
        await logger.error(f"Orchestration failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Advocacy Engine Error: {str(e)}"
        )

# ... (Keep your existing admin_upload and check_db endpoints as they were)

```

---

### 2. The New Service Layer (`app/services/orchestrator_service.py`)

*This is the "Brain" or the Semantic Router you asked for. It analyzes intent and dispatches tasks.*

```python
from app.services.advocacy_service import query_advocacy_engine  # Your existing RAG
# from app.services.external_tools import google_search_tool, npi_lookup_tool (Hypothetical)
from app.utils.logger import get_logger

logger = get_logger(__name__)

class AdvocacyOrchestrator:
    """
    The Traffic Controller.
    Decides if a query is about a specific Plan (Private Data) or General Medical Info (Public Data).
    """

    async def classify_intent(self, query: str) -> str:
        """
        Simple keyword/heuristic classifier. 
        In production, replace this with a lightweight LLM call or Semantic Router.
        """
        query_lower = query.lower()
        
        # 1. Action Intents
        if any(x in query_lower for x in ["find a doctor", "provider", "npi", "verify doctor"]):
            return "PROVIDER_LOOKUP"
        
        # 2. Private Plan Intents (The "My Plan" queries)
        private_keywords = ["my plan", "coverage", "deductible", "copay", "claim", "denial", "appeal", "cost"]
        if any(x in query_lower for x in private_keywords):
            return "PLAN_RAG"

        # 3. General Medical Intents
        general_keywords = ["symptoms", "side effects", "treatment for", "what is"]
        if any(x in query_lower for x in general_keywords):
            return "GENERAL_WEB"

        # Default fallback to Plan RAG if unsure (Safety first)
        return "PLAN_RAG"

    async def process_user_query(self, query: str, tenant_id: str, plan_id: str) -> dict:
        """
        Main routing logic.
        """
        intent = await self.classify_intent(query)
        await logger.info(f"Intent classified as: {intent}")

        # --- ROUTE 1: PRIVATE PLAN DATA (Your existing RAG) ---
        if intent == "PLAN_RAG":
            await logger.info("Routing to Internal RAG...")
            return await query_advocacy_engine(query, tenant_id, plan_id)

        # --- ROUTE 2: EXTERNAL WEB SEARCH ---
        elif intent == "GENERAL_WEB":
            await logger.info("Routing to General Medical Search...")
            # Placeholder for Google/PubMed Search Service
            # result = await google_search_service(query) 
            return {
                "answer": "This appears to be a general medical question. [Simulated Web Search Result]: Standard treatment involves...",
                "sources": ["PubMed", "Mayo Clinic"],
                "intent": "general_knowledge"
            }

        # --- ROUTE 3: ACTION / TOOLS ---
        elif intent == "PROVIDER_LOOKUP":
            await logger.info("Routing to Provider Lookup Tool...")
            # Placeholder for NPI Registry API call
            return {
                "answer": "I can help you find a doctor. Please provide the specialty and zip code.",
                "sources": ["NPI Registry"],
                "intent": "tool_use"
            }
        
        else:
            return {"answer": "I'm not sure how to route this request.", "sources": []}

```

### Why this is better:

1. **Cleaner Code:** Your FastAPI router is now 30 lines instead of 100.
2. **Scalability:** If you want to add a "Drug Interaction Checker" later, you just add an `elif` in the `Orchestrator`, you don't touch the API endpoint.
3. **Security:** You can now clearly see where PHI (Private Health Info) is going. You can add a check inside `GENERAL_WEB` route to strip names before sending to Google.

**Next Step:**
Would you like the code for the **"Intent Classifier"** to use an actual LLM (e.g., "Is this query asking about specific insurance benefits or general medical advice?") instead of just keywords?