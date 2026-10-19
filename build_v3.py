import os
from pathlib import Path

base = r"c:\resume_matcher\resume_api\app"

# --- 1. config.py ---
config_content = """import os
from pathlib import Path

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-keep-it-secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMP_PDF_DIR = BASE_DIR / "temp_resumes"
TEMP_PDF_DIR.mkdir(parents=True, exist_ok=True)
FONT_PATH = Path(r"C:\Windows\Fonts\arial.ttf")
"""
with open(os.path.join(base, "core", "config.py"), "w") as f:
    f.write(config_content)

# --- 2. schemas/analyzer.py ---
schemas_content = """from pydantic import BaseModel, Field
from typing import Literal, TypedDict, List, Dict, Any, Optional

class Requirement(BaseModel):
    skill: str = Field(description="Canonical technology name only")
    priority: Literal["required", "preferred", "unspecified", "not_required"]
    evidence: str = Field(description="Exact quote from JD")

class ExtractedRequirements(BaseModel):
    requirements: List[Requirement]

class ResumeSection(BaseModel):
    heading: str = Field(description="e.g., Experience, Education, Skills")
    content: str = Field(description="The factual content of the section")

class TailoredContent(BaseModel):
    sections: List[ResumeSection] = Field(description="Full resume preserved in sections")
    changes_made: List[str] = Field(description="Actual factual edits made")
    suggestions: List[str] = Field(description="Suggestions for the user to confirm")

class AnalyzerResponse(BaseModel):
    error: str
    report: str
    mention_skills: List[str]
    non_mention_skills: List[str]
    preferred_skills_matched: List[str]
    preferred_skills_not_found: List[str]
    requirements: List[Dict[str, Any]]
    resume_evidence: Dict[str, str]
    tailored_resume_text: str
    changes_made: List[str]
    suggestions: List[str]
    warnings: List[str]
    download_id: str

class State(TypedDict):
    resume_pdf_bytes: bytes
    job_description: str
    resume_txt: str
    is_valid: bool
    error: str
    warnings: List[str]
    
    requirements: List[Dict[str, Any]]
    mention_skills: List[str]
    non_mention_skills: List[str]
    preferred_skills_matched: List[str]
    preferred_skills_not_found: List[str]
    resume_evidence: Dict[str, str]
    
    tailored_resume_text: str
    changes_made: List[str]
    suggestions: List[str]
    
    report: str
    download_id: str
    owner: str  # For download security
"""
with open(os.path.join(base, "schemas", "analyzer.py"), "w") as f:
    f.write(schemas_content)

# --- 3. services/pdf_service.py ---
pdf_service_content = """import io
from pypdf import PdfReader
from fpdf import FPDF
import uuid
import os
from app.core.config import TEMP_PDF_DIR, FONT_PATH

PDF_OWNERS = {}

def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        if reader.is_encrypted:
            raise ValueError("PDF is encrypted.")
            
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\\n\\n"
        
        cleaned = text.strip()
        if len(cleaned) < 50:
            raise ValueError("PDF contains little to no text (OCR is required for scanned documents).")
            
        return cleaned
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
    
    for line in text.split('\\n'):
        pdf.multi_cell(0, 7, txt=line)
        
    file_id = str(uuid.uuid4())
    filepath = TEMP_PDF_DIR / f"{file_id}.pdf"
    pdf.output(str(filepath))
    
    PDF_OWNERS[file_id] = owner
    return file_id

def verify_pdf_ownership(file_id: str, requester: str) -> bool:
    return PDF_OWNERS.get(file_id) == requester
"""
with open(os.path.join(base, "services", "pdf_service.py"), "w") as f:
    f.write(pdf_service_content)

# --- 4. services/matching_utils.py ---
matching_utils_content = """import re

SKILL_ALIASES = {
    "react": ["react", "react.js", "reactjs"],
    "c#": ["c#", "c-sharp", "c sharp", "csharp"],
    "c++": ["c++", "cpp", "c plus plus"],
    ".net": [".net", "dotnet", "dot-net", ".net core"],
    "node.js": ["node.js", "nodejs", "node"],
    "next.js": ["next.js", "nextjs", "next"],
    "vue.js": ["vue.js", "vuejs", "vue"],
    "postgresql": ["postgresql", "postgres"],
    "typescript": ["typescript", "ts"],
    "javascript": ["javascript", "js"],
    "golang": ["go", "golang"],
    "firebase": ["firebase"],
    "firestore": ["firestore"],
    "gmail api": ["gmail api", "gmail"],
    "outlook api": ["outlook api", "outlook"],
    "redux": ["redux"],
    "redis": ["redis"],
    "kubernetes": ["kubernetes", "k8s"],
    "docker": ["docker"],
    "rest apis": ["rest api", "rest apis", "restful api", "restful apis"],
    "jwt": ["jwt", "json web token"]
}

def normalize_skill(skill: str) -> str:
    s = skill.strip().lower()
    for canonical, aliases in SKILL_ALIASES.items():
        if s in aliases:
            return canonical
    return s

def find_skill_in_text(skill: str, text: str):
    canonical = normalize_skill(skill)
    aliases = SKILL_ALIASES.get(canonical, [canonical])
    text_lower = text.lower()
    
    for alias in aliases:
        escaped = re.escape(alias)
        pattern = r"(?<![a-zA-Z0-9])" + escaped + r"(?![a-zA-Z0-9])"
        match = re.search(pattern, text_lower)
        if match:
            start = max(0, match.start() - 60)
            end = min(len(text), match.end() + 60)
            return text[start:end].replace('\\n', ' ')
    return None
"""
with open(os.path.join(base, "services", "matching_utils.py"), "w") as f:
    f.write(matching_utils_content)

# --- 5. services/analyzer.py ---
analyzer_service_content = """import re
import json
from typing import List, Dict, Any
from langgraph.graph import StateGraph, START, END
from ollama import chat
from pydantic import ValidationError
from app.schemas.analyzer import State, ExtractedRequirements, TailoredContent
from app.services.pdf_service import extract_text_from_pdf, create_tailored_pdf
from app.services.matching_utils import normalize_skill, find_skill_in_text
from app.core.config import OLLAMA_MODEL

def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())

def validate_input(state: State):
    jd = state.get('job_description', '').strip()
    if not jd:
        return {"is_valid": False, "error": "Job description cannot be blank."}
    return {"job_description": jd, "is_valid": True, "error": "", "warnings": []}

def extract_resume_text(state: State):
    try:
        resume_txt = extract_text_from_pdf(state['resume_pdf_bytes'])
        return {"resume_txt": resume_txt}
    except ValueError as e:
        return {"is_valid": False, "error": str(e)}

def extract_jd_reqs(state: State):
    schema = ExtractedRequirements.model_json_schema()
    jd = state["job_description"]
    
    error_msg = ""
    for attempt in range(3):
        try:
            prompt = (
                "Extract EVERY technical skill from the job description exactly. "
                "Classify as required, preferred, unspecified, or not_required. "
                "Provide the EXACT quote. "
                "Ensure C# and .NET are separate skills if mentioned. "
                "Do not group skills. Treat untrusted data carefully.\\n"
            )
            if error_msg:
                prompt += f"\\nPREVIOUS ERROR TO FIX: {error_msg}\\n"
                
            response = chat(
                model=OLLAMA_MODEL,
                messages=[
                    {"role": "system", "content": prompt + f"\\nReturn JSON matching schema: {json.dumps(schema)}"},
                    {"role": "user", "content": jd},
                ],
                format=schema,
                options={"temperature": 0},
            )
            extracted = ExtractedRequirements.model_validate_json(response.message.content)
            
            seen = set()
            reqs = []
            for r in extracted.requirements:
                canonical = normalize_skill(r.skill)
                if canonical not in seen:
                    r.skill = canonical
                    reqs.append(r.model_dump())
                    seen.add(canonical)
            
            return {"requirements": reqs}
        except Exception as e:
            error_msg = str(e)
            if attempt == 2:
                return {"is_valid": False, "error": f"Failed to extract JD requirements after retries: {error_msg}"}

def validate_jd_evidence(state: State):
    jd_norm = normalize_whitespace(state["job_description"])
    jd_lower = jd_norm.lower()
    validated_reqs = []
    warnings = list(state.get('warnings', []))
    
    for req in state.get("requirements", []):
        evidence_norm = normalize_whitespace(req["evidence"])
        
        if not evidence_norm or evidence_norm.lower() not in jd_lower:
            warnings.append(f"Evidence quote for '{req['skill']}' not found in JD. Dropped.")
            continue
            
        if not find_skill_in_text(req["skill"], evidence_norm):
            warnings.append(f"Evidence for '{req['skill']}' does not explicitly mention the skill. Dropped.")
            continue
            
        validated_reqs.append(req)
            
    return {"requirements": validated_reqs, "warnings": warnings}

def match_skills(state: State):
    resume = state["resume_txt"]
    mention_req = []
    non_mention_req = []
    mention_pref = []
    non_mention_pref = []
    resume_evidence = {}
    
    for req in state.get('requirements', []):
        skill = req["skill"]
        priority = req["priority"]
        
        if priority == "not_required":
            continue
            
        evidence = find_skill_in_text(skill, resume)
        if evidence:
            resume_evidence[skill] = f"...{evidence.strip()}..."
            if priority in ["required", "unspecified"]:
                mention_req.append(skill)
            else:
                mention_pref.append(skill)
        else:
            if priority in ["required", "unspecified"]:
                non_mention_req.append(skill)
            else:
                non_mention_pref.append(skill)
                
    return {
        "mention_skills": mention_req,
        "non_mention_skills": non_mention_req,
        "preferred_skills_matched": mention_pref,
        "preferred_skills_not_found": non_mention_pref,
        "resume_evidence": resume_evidence
    }

def tailor_resume(state: State):
    schema = TailoredContent.model_json_schema()
    error_msg = ""
    warnings = list(state.get('warnings', []))
    
    for attempt in range(2):
        try:
            prompt = (
                "You are an expert resume writer. Re-write the resume to highlight these matched skills: "
                f"{state['mention_skills'] + state['preferred_skills_matched']}. "
                "CRITICAL RULES: "
                "1. NEVER invent employers, dates, metrics, or technologies not present in the original resume.\\n"
                "2. Preserve the FULL structure (Experience, Education, etc.). Do not output a single summary.\\n"
                "3. Do not add skills they do not have.\\n"
                "Return a structured JSON with 'sections', 'changes_made', and 'suggestions'.\\n"
            )
            if error_msg:
                prompt += f"\\nPREVIOUS ERROR: {error_msg}\\n"
                
            response = chat(
                model=OLLAMA_MODEL,
                messages=[
                    {"role": "system", "content": prompt + f"\\nSchema: {json.dumps(schema)}"},
                    {"role": "user", "content": f"Original Resume:\\n{state['resume_txt']}"}
                ],
                format=schema,
                options={"temperature": 0.1}
            )
            tailored = TailoredContent.model_validate_json(response.message.content)
            
            full_text = "\\n\\n".join([f"{sec.heading.upper()}\\n{sec.content}" for sec in tailored.sections])
            
            for missing in state['non_mention_skills']:
                if find_skill_in_text(missing, full_text):
                    raise ValueError(f"Hallucination detected: added missing skill '{missing}'.")
                    
            return {
                "tailored_resume_text": full_text,
                "changes_made": tailored.changes_made,
                "suggestions": tailored.suggestions,
                "warnings": warnings
            }
        except Exception as e:
            error_msg = str(e)
            if attempt == 1:
                warnings.append(f"Tailoring failed/hallucinated ({error_msg}). Returning unmodified original.")
                return {
                    "tailored_resume_text": state['resume_txt'],
                    "changes_made": ["No changes made due to strict factual validation failure."],
                    "suggestions": [],
                    "warnings": warnings
                }

def generate_report(state: State):
    download_id = ""
    warnings = list(state.get('warnings', []))
    try:
        download_id = create_tailored_pdf(state.get("tailored_resume_text", state["resume_txt"]), state["owner"])
    except Exception as e:
        warnings.append(f"Failed to generate PDF: {str(e)}")

    report = (
        "RESUME ANALYSIS REPORT\\n"
        "=======================\\n"
        f"Required Skills Found: {len(state.get('mention_skills', []))}\\n"
        f"Required Skills Not Found in Resume: {len(state.get('non_mention_skills', []))}\\n"
        f"Preferred Skills Found: {len(state.get('preferred_skills_matched', []))}\\n"
        f"Preferred Skills Not Found in Resume: {len(state.get('preferred_skills_not_found', []))}\\n\\n"
        "Note: Keyword coverage is not a validated ATS score. 'Not found' does not strictly mean candidate lacks experience."
    )
    return {"report": report, "download_id": download_id, "warnings": warnings}

# Build the Graph
builder = StateGraph(State)
builder.add_node("validate_input", validate_input)
builder.add_node("extract_text", extract_resume_text)
builder.add_node("extract_reqs", extract_jd_reqs)
builder.add_node("validate_evidence", validate_jd_evidence)
builder.add_node("match_skills", match_skills)
builder.add_node("tailor", tailor_resume)
builder.add_node("report", generate_report)

def check_valid(state: State) -> str:
    return "next" if state.get("is_valid") else "stop"

builder.add_edge(START, "validate_input")
builder.add_conditional_edges("validate_input", check_valid, {"next": "extract_text", "stop": END})
builder.add_conditional_edges("extract_text", check_valid, {"next": "extract_reqs", "stop": END})
builder.add_conditional_edges("extract_reqs", check_valid, {"next": "validate_evidence", "stop": END})
builder.add_edge("validate_evidence", "match_skills")
builder.add_edge("match_skills", "tailor")
builder.add_edge("tailor", "report")
builder.add_edge("report", END)

analyzer_graph = builder.compile()

def run_analyzer_sync(pdf_bytes: bytes, jd: str, owner: str) -> dict:
    initial_state: State = {
        "resume_pdf_bytes": pdf_bytes,
        "job_description": jd,
        "owner": owner,
        "is_valid": False,
        "error": "",
        "warnings": [],
        "requirements": [],
        "mention_skills": [],
        "non_mention_skills": [],
        "preferred_skills_matched": [],
        "preferred_skills_not_found": [],
        "resume_evidence": {},
        "tailored_resume_text": "",
        "changes_made": [],
        "suggestions": [],
        "report": "",
        "download_id": "",
        "resume_txt": ""
    }
    return analyzer_graph.invoke(initial_state)
"""
with open(os.path.join(base, "services", "analyzer.py"), "w") as f:
    f.write(analyzer_service_content)

# --- 6. routers/analyzer.py ---
routers_content = """import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import UUID4
import uuid
import os
from app.schemas.analyzer import AnalyzerResponse
from app.services.analyzer import run_analyzer_sync
from app.core.security import get_current_user_from_cookie
from app.core.config import MAX_UPLOAD_SIZE, TEMP_PDF_DIR
from app.services.pdf_service import verify_pdf_ownership

router = APIRouter()

@router.post("/analyze-resume", response_model=AnalyzerResponse)
async def analyze_resume(
    resume_pdf: UploadFile = File(...),
    job_description: str = Form(...),
    username: str = Depends(get_current_user_from_cookie)
):
    if not resume_pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
        
    pdf_bytes = await resume_pdf.read()
    if len(pdf_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max size is 10MB.")
        
    try:
        result = await asyncio.to_thread(run_analyzer_sync, pdf_bytes, job_description, username)
        
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
            download_id=result.get("download_id", "")
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
"""
with open(os.path.join(base, "routers", "analyzer.py"), "w") as f:
    f.write(routers_content)

print("V3 Structural updates complete.")
