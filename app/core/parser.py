# app/services/parser.py
from llama_parse import LlamaParse
from llama_index.core import SimpleDirectoryReader
import os

def get_medical_parser():
    return LlamaParse(
        api_key=os.getenv("LLAMA_CLOUD_API_KEY"),
        result_type="markdown",
        parsing_instruction="Extract insurance tables. Keep In-Network vs Out-of-Network clear."
    )

async def parse_pdf_to_docs(file_path: str, plan_id: str):
    parser = get_medical_parser()
    # aload_data returns a list of Document objects
    documents = await SimpleDirectoryReader(
        input_files=[file_path], 
        file_extractor={".pdf": parser}
    ).aload_data()
    
    # Tagging the documents for multi-tenancy
    for doc in documents:
        doc.metadata = {"plan_id": plan_id, "source": os.path.basename(file_path)}
    return documents
    