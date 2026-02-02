from llama_index.core.llms import LLM
from llama_index.llms.openai import OpenAI
from llama_index.core import PromptTemplate
from app.schemas.intent_schema import UserIntent, IntentRouting
from app.prompts.intent_prompt import INTENT_CLASSIFICATION_PROMPT
from app.core.data import OPENAI_API_KEY

async def classify_intent_with_confidence(query: str) -> IntentRouting:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY must be set")
    
    llm = OpenAI(
        model="gpt-4o-mini",
        api_key=OPENAI_API_KEY,
        temperature=0.1
    )
    
    prompt_template = PromptTemplate(INTENT_CLASSIFICATION_PROMPT)
    
    response = await llm.astructured_predict(
        IntentRouting,
        prompt_template,
        query=query
    )
    return response