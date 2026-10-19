import io
import re
from pypdf import PdfReader
from fpdf import FPDF
from fpdf.enums import XPos, YPos
import uuid
import os
from app.core.config import TEMP_PDF_DIR, FONT_PATH

PDF_OWNERS = {}

def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        if reader.is_encrypted:
            raise ValueError("PDF is encrypted.")
            
        pages = []
        for page in reader.pages:
            # Layout mode does a substantially better job on multi-column resumes.
            # Fall back for PDFs whose content stream cannot be handled in that mode.
            try:
                page_text = page.extract_text(extraction_mode="layout")
            except (TypeError, ValueError):
                page_text = page.extract_text()
            if page_text:
                pages.append(page_text)
        
        cleaned = "\n\n".join(pages).strip()
        if not cleaned:
            raise ValueError("PDF has no extractable text. Upload a text-based PDF or run OCR on the scanned document first.")
        if len(re.sub(r"\s+", "", cleaned)) < 10:
            raise ValueError("PDF contains too little readable text to analyze reliably.")
            
        return cleaned
    except ValueError as e:
        if str(e).startswith("Failed to read PDF:"):
            raise
        raise ValueError(f"Failed to read PDF: {str(e)}") from e
    except Exception as e:
        raise ValueError(f"Failed to read PDF: {str(e)}")

def create_tailored_pdf(text: str, owner: str) -> str:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    if FONT_PATH.exists():
        pdf.add_font("ArialUni", "", str(FONT_PATH), uni=True)
        pdf.set_font("ArialUni", size=11)
    else:
        pdf.set_font("Arial", size=11)
    
    for line in text.split('\n'):
        pdf.multi_cell(0, 7, text=line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
    file_id = str(uuid.uuid4())
    filepath = TEMP_PDF_DIR / f"{file_id}.pdf"
    pdf.output(str(filepath))
    
    PDF_OWNERS[file_id] = owner
    return file_id

def verify_pdf_ownership(file_id: str, requester: str) -> bool:
    return PDF_OWNERS.get(file_id) == requester
