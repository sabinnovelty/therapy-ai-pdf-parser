import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.prompts.summarization_prompts import ADVOCATE_SUMMARY_TEMPLATE
from app.schemas.summarization_schema import SummarizationRequest


# 1. Initialize once. Using gpt-4o-mini is already the best token-to-cost ratio.
llm_mini = ChatOpenAI(model="gpt-4o-mini", temperature=0)

class SummarizationService:
    @staticmethod
    async def summarize(request: SummarizationRequest) -> str:
        # 2. Extreme Token Optimization: Minimize the JSON payload
        # We only send text; no IDs or redundant metadata
        # Extract only note and createdBy.name from the full note object
        case_data = json.dumps({
            "pnt": request.patientName,
            "status": request.currentCaseStatus,
            "notes": [{"n": n.note, "by": n.createdBy.name} for n in request.notes]
        }, separators=(',', ':')) # Separators remove whitespace for token saving

        # 3. Choose Persona-Driven Template
        template_str = ADVOCATE_SUMMARY_TEMPLATE
        
        # 4. LCEL Chain with strict token limit
        prompt = PromptTemplate.from_template(template_str)
        # Setting max_tokens here forces the model to stop if it gets too long
        chain = prompt | llm_mini.with_config({"max_tokens": 300}) | StrOutputParser()

        summary = await chain.ainvoke({
            "case_data": case_data,
        })

        return summary.strip()