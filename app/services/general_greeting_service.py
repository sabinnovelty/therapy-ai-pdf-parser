from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.prompts.greeting_prompt import GREETING_TEMPLATE
from app.core.llm import get_chat_llm_mini
from app.utils.logger import logger

async def generate_greeting_response() -> dict:
    llm_mini = get_chat_llm_mini(temperature=0.7)
    prompt = PromptTemplate.from_template(GREETING_TEMPLATE)
    chain = prompt | llm_mini | StrOutputParser()
    
    answer = await chain.ainvoke({})
    
    return {
        "answer": answer.strip(),
        "sources": []
    }
