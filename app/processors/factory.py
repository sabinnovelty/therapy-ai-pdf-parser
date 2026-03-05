from app.processors.pdf_text_processor import PDFTextProcessor
from app.processors.base import BaseFileProcessor

class ProcessorFactory:
    @staticmethod
    def get_processor(processor_type:str)->BaseFileProcessor:
        if processor_type == "pdf_text":
            return PDFTextProcessor()
        else:
            raise ValueError(f"Unsupported processor type: {processor_type}")