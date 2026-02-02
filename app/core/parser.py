import os
import asyncio
from llama_index.core import Document
from llama_parse import LlamaParse
from typing import List
from app.core.data import LLAMA_API_KEY
from app.utils.logger import get_logger

logger = get_logger(__name__)


class LlamaParsePDFParser:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or LLAMA_API_KEY
        if not self.api_key:
            raise ValueError("LLAMA_API_KEY must be set in environment variables")
        
        self.parser = LlamaParse(
            api_key=self.api_key,
            result_type="markdown",
            verbose=True
        )
    
    async def parse_file(self, file_path: str) -> str:
        try:
            logger.info(f"Parsing PDF with LlamaParse: {file_path}")
            
            loop = asyncio.get_event_loop()
            documents = await loop.run_in_executor(None, self.parser.load_data, file_path)
            
            if not documents or len(documents) == 0:
                raise ValueError("No content extracted from PDF")
            
            text_content = "\n\n".join([doc.text for doc in documents if doc.text])
            
            if not text_content:
                raise ValueError("No text content extracted from PDF")
            
            logger.info(f"Successfully extracted text from PDF: {len(text_content)} characters")
            return text_content
            
        except Exception as e:
            logger.error(f"Error parsing PDF {file_path} with LlamaParse: {str(e)}", exc_info=True)
            raise


def get_parser(api_key: str = None):
    return LlamaParsePDFParser(api_key=api_key)


async def parse_pdf_to_docs(file_path: str, category: str, tenant_id: str) -> List[Document]:
    parser = get_parser()
    
    text_content = await parser.parse_file(file_path)
    
    document = Document(
        text=text_content,
        metadata={
            "tenant_id": tenant_id,
            "category": category,
            "source": os.path.basename(file_path),
            "file_path": file_path
        }
    )
    
    return [document]
    