import os
import aiofiles

async def save_to_disk(file:bytes,file_path:str)->bool:
    try:
        os.makedirs(os.path.dirname(file_path),exist_ok=True)
        async with aiofiles.open(file_path,'wb') as f:
            await f.write(file)
        return True
    except Exception as e:
        raise

def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from a PDF file using PyMuPDF (fitz). Supports relative paths (e.g. storage/uploads/...)."""
    import fitz
    path = os.path.abspath(file_path)
    doc = fitz.open(path)
    full_text = ""
    try:
        for page in doc:
            full_text += page.get_text("text") + "\n"
    finally:
        doc.close()
    return full_text