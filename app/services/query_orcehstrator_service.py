import asyncio
from app.services.intent_service import classify_intent_with_confidence
from app.services.advocacy_service import query_advocacy_engine
from app.services.search_service import general_medical_search, web_search, other_search
from app.services.general_greeting_service import generate_greeting_response
from app.utils.logger import logger

class QueryOrchestrator:
    def __init__(self, threshold: float = 0.75):
        self.threshold = threshold

    async def process_user_query(self, query: str, tenant_id: str, plan_id: str) -> dict:
        routing = await classify_intent_with_confidence(query)
        intent = routing.intent
        confidence = routing.confidence

        # 2. LOW CONFIDENCE BRANCH: Hybrid Ensemble
        if confidence < self.threshold:
            await logger.warning(f"Low confidence ({confidence}). Executing Hybrid Ensemble.")
            
            plan_task = query_advocacy_engine(query, tenant_id, plan_id)
            web_task = general_medical_search(query) 
            
            plan_res, web_res = await asyncio.gather(plan_task, web_task)
            
            return await self.synthesize_hybrid_response(query, plan_res, web_res)

        # 3. HIGH CONFIDENCE BRANCH: Single Path
        await logger.info(f"High confidence ({confidence}) for intent: {intent}")
        return await self.execute_single_path(intent, query, tenant_id, plan_id)

    async def execute_single_path(self, intent: str, query: str, tenant_id: str, plan_id: str):
        if intent == "plan_specific":
            return await query_advocacy_engine(query, tenant_id, plan_id)
        elif intent == "general_web":
            return await web_search(query)
        elif intent == "general_health":
            return await general_medical_search(query)
        elif intent == "greeting":
            return await generate_greeting_response()
        elif intent == "other":
            return await other_search(query)
        else:
            await logger.warning(f"Unknown intent: {intent}. Falling back to general medical search.")
            return await general_medical_search(query)


    async def synthesize_hybrid_response(self, query: str, plan_data: dict, web_data: dict) -> dict:
        # Call LLM with a specialized 'synthesis' prompt
        # answer = await llm.synthesize(query, plan_data, web_data)
        return {
            "answer": "I found information in both your plan and general medical records...",
            "sources": plan_data.get("sources", []) + web_data.get("sources", []),
            "mode": "hybrid_ensemble"
        }