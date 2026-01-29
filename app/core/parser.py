# app/core/parser.py
import os
import time
from openai import OpenAI
from llama_index.core import Document
from typing import List
from app.utils.logger import get_logger

logger = get_logger(__name__)


class OpenAIPDFParser:
    """
    PDF parser using OpenAI's File API and Assistants API for direct PDF text extraction.
    OpenAI handles PDF parsing internally, including tables and complex layouts.
    Uses Assistants API with file inputs to extract all text content.
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialize OpenAI client for PDF parsing.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
        """
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
    
    async def parse_file(self, file_path: str) -> str:
        """
        Parse PDF file using OpenAI's File API and Assistants API.
        OpenAI handles PDF parsing internally, extracting text, tables, and structure.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Extracted text content as markdown-formatted string
        """
        try:
            logger.info(f"Uploading PDF to OpenAI for parsing: {file_path}")
            
            # Upload PDF file to OpenAI
            with open(file_path, "rb") as pdf_file:
                file_response = self.client.files.create(
                    file=pdf_file,
                    purpose="assistants"  # Use assistants purpose for PDF processing
                )
            
            file_id = file_response.id
            logger.info(f"PDF uploaded to OpenAI, file_id: {file_id}")
            
            # Wait for file to be processed
            max_wait_time = 60  # Maximum wait time in seconds
            wait_time = 0
            while wait_time < max_wait_time:
                file_status = self.client.files.retrieve(file_id)
                if file_status.status == "processed":
                    break
                elif file_status.status == "error":
                    self.client.files.delete(file_id)
                    raise ValueError(f"OpenAI file processing failed: {file_status.error}")
                time.sleep(2)
                wait_time += 2
            
            if wait_time >= max_wait_time:
                self.client.files.delete(file_id)
                raise TimeoutError("File processing timed out")
            
            # Extract text content using Assistants API with file input
            # OpenAI's Assistants API supports file_ids parameter for file processing
            # Create a temporary assistant to process the file
            assistant = self.client.beta.assistants.create(
                name="PDF Parser",
                instructions="You are a PDF text extraction assistant. Extract and return all text content from PDF documents. Preserve the structure, including tables, headers, and formatting. Format tables as markdown tables. Return only the extracted content without additional commentary.",
                model="gpt-4o-mini",  # Use cost-effective model for extraction
                tools=[{"type": "file_search"}]
            )
            
            try:
                # Create a thread and add the file
                thread = self.client.beta.threads.create(
                    messages=[
                        {
                            "role": "user",
                            "content": "Please extract and return all text content from this PDF document. Preserve the structure, including tables, headers, and formatting. Format tables as markdown tables. Return only the extracted content without additional commentary.",
                            "attachments": [
                                {
                                    "file_id": file_id,
                                    "tools": [{"type": "file_search"}]
                                }
                            ]
                        }
                    ]
                )
                
                # Run the assistant
                run = self.client.beta.threads.runs.create(
                    thread_id=thread.id,
                    assistant_id=assistant.id
                )
                
                # Wait for the run to complete
                max_wait_time = 120  # Maximum wait time in seconds
                wait_time = 0
                while wait_time < max_wait_time:
                    run_status = self.client.beta.threads.runs.retrieve(
                        thread_id=thread.id,
                        run_id=run.id
                    )
                    if run_status.status == "completed":
                        break
                    elif run_status.status == "failed":
                        error_msg = getattr(run_status, 'last_error', None)
                        if error_msg:
                            error_details = getattr(error_msg, 'message', str(error_msg))
                        else:
                            error_details = "Unknown error"
                        raise ValueError(f"Assistant run failed: {error_details}")
                    time.sleep(2)
                    wait_time += 2
                
                if wait_time >= max_wait_time:
                    raise TimeoutError("Assistant run timed out")
                
                # Retrieve the messages from the thread
                messages = self.client.beta.threads.messages.list(thread_id=thread.id)
                text_content = ""
                if messages.data and len(messages.data) > 0:
                    # Get the assistant's response (first message should be the assistant's response)
                    for message in messages.data:
                        if message.role == "assistant":
                            if message.content and len(message.content) > 0:
                                # Extract text from content blocks
                                for content_block in message.content:
                                    if hasattr(content_block, 'text') and content_block.text:
                                        text_content = content_block.text.value
                                        break
                            break
                
                if not text_content:
                    raise ValueError("No text content extracted from PDF")
                    
            finally:
                # Clean up: delete assistant and thread
                try:
                    self.client.beta.assistants.delete(assistant.id)
                except:
                    pass
                try:
                    if 'thread' in locals():
                        self.client.beta.threads.delete(thread.id)
                except:
                    pass
            
            # Clean up: delete the file from OpenAI
            self.client.files.delete(file_id)
            
            logger.info(f"Successfully extracted text from PDF: {len(text_content)} characters")
            return text_content
            
        except Exception as e:
            logger.error(f"Error parsing PDF {file_path} with OpenAI: {str(e)}", exc_info=True)
            # Try to clean up file if it exists
            try:
                if 'file_id' in locals():
                    self.client.files.delete(file_id)
            except:
                pass
            raise


def get_medical_parser(api_key: str = None):
    """
    Get the PDF parser instance.
    Uses OpenAI's File API for direct PDF parsing.
    
    Args:
        api_key: Optional OpenAI API key (defaults to OPENAI_API_KEY env var)
    """
    return OpenAIPDFParser(api_key=api_key)


async def parse_pdf_to_docs(file_path: str, plan_id: str) -> List[Document]:
    """
    Parse PDF file using OpenAI's File API and return LlamaIndex Document objects.
    
    Args:
        file_path: Path to the PDF file
        plan_id: Plan identifier for metadata tagging
        
    Returns:
        List of Document objects
    """
    parser = get_medical_parser()
    
    # Parse PDF to text using OpenAI's File API
    text_content = await parser.parse_file(file_path)
    
    # Create Document object with metadata
    document = Document(
        text=text_content,
        metadata={
            "plan_id": plan_id,
            "source": os.path.basename(file_path),
            "file_path": file_path
        }
    )
    
    return [document]
    