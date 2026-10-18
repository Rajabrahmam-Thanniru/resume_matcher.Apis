import asyncio
from time import perf_counter
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import UUID4
import uuid
import os
from app.schemas.analyzer import AnalyzerResponse
from app.services.analyzer import run_analyzer_sync
from app.core.security import get_current_user_from_cookie
from app.core.config import MAX_UPLOAD_SIZE, TEMP_PDF_DIR, ANALYSIS_TIMEOUT_SECONDS
from app.services.pdf_service import verify_pdf_ownership

router = APIRouter()

@router.post("/analyze-resume", response_model=AnalyzerResponse)
async def analyze_resume(
    resume_pdf: UploadFile = File(...),
    job_description: str = Form(...),
    username: str = Depends(get_current_user_from_cookie),
    tailor: bool = Form(True),
):
    started_at = perf_counter()
    if not resume_pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
        
    pdf_bytes = await resume_pdf.read()
    if len(pdf_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max size is 10MB.")
        
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(run_analyzer_sync, pdf_bytes, job_description, username, tailor),
            timeout=ANALYSIS_TIMEOUT_SECONDS,
        )
        
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])
            
        return AnalyzerResponse(
            error=result.get("error", ""),
            report=result.get("report", ""),
            mention_skills=result.get("mention_skills", []),
            non_mention_skills=result.get("non_mention_skills", []),
            preferred_skills_matched=result.get("preferred_skills_matched", []),
            preferred_skills_not_found=result.get("preferred_skills_not_found", []),
            requirements=result.get("requirements", []),
            resume_evidence=result.get("resume_evidence", {}),
            tailored_resume_text=result.get("tailored_resume_text", ""),
            changes_made=result.get("changes_made", []),
            suggestions=result.get("suggestions", []),
            warnings=result.get("warnings", []),
            download_id=result.get("download_id", ""),
            response_time_seconds=round(perf_counter() - started_at, 3)
        )
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail=str(exc) or "Resume analysis exceeded its overall time limit. Try tailor=false to skip resume rewriting.",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="An internal server error occurred.")

@router.get("/download-resume/{file_id}")
async def download_resume(
    file_id: str,
    username: str = Depends(get_current_user_from_cookie)
):
    try:
        uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file ID format.")
        
    if not verify_pdf_ownership(file_id, username):
        raise HTTPException(status_code=403, detail="Not authorized to download this file.")

    file_path = TEMP_PDF_DIR / f"{file_id}.pdf"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Resume not found or has expired.")
        
    return FileResponse(
        path=file_path, 
        filename=f"tailored_resume_{username}.pdf",
        media_type="application/pdf"
    )
