import os

base = r"c:\resume_matcher\resume_api\app"

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

def extract_and_validate_jd_reqs(state: State):
    schema = ExtractedRequirements.model_json_schema()
    jd = state["job_description"]
    jd_lower = normalize_whitespace(jd).lower()
    warnings = list(state.get('warnings', []))
    
    error_msg = ""
    for attempt in range(3):
        try:
            prompt = (
                "Extract EVERY technical skill from the job description exactly. "
                "Classify as required, preferred, unspecified, or not_required. "
                "Provide the EXACT quote from the text. "
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
            
            # Validation Step
            seen = set()
            reqs = []
            bad_evidence = []
            
            for r in extracted.requirements:
                canonical = normalize_skill(r.skill)
                # Deduplicate
                if canonical in seen:
                    continue
                    
                evidence_norm = normalize_whitespace(r.evidence)
                
                # Check quote exists
                if not evidence_norm or evidence_norm.lower() not in jd_lower:
                    bad_evidence.append(f"Quote '{r.evidence}' for {r.skill} not found exactly in JD.")
                    continue
                    
                # Check quote actually mentions skill
                if not find_skill_in_text(r.skill, evidence_norm):
                    bad_evidence.append(f"Quote '{r.evidence}' for {r.skill} does not mention the skill.")
                    continue
                    
                # Passed validation
                r.skill = canonical
                reqs.append(r.model_dump())
                seen.add(canonical)
            
            if bad_evidence and attempt < 2:
                error_msg = "\\n".join(bad_evidence)
                continue # Retry
                
            if bad_evidence:
                warnings.append("Extraction validation failed after retries for some skills.")
            
            return {"requirements": reqs, "warnings": warnings}
            
        except Exception as e:
            error_msg = str(e)
            if attempt == 2:
                return {"is_valid": False, "error": f"Failed to extract JD requirements after retries: {error_msg}"}
                
    return {"is_valid": False, "error": "Extraction fallback failed."}


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
                "2. Preserve the FULL structure including Name, Contact Details, Summary, Employment, Projects, Education, and Skills.\\n"
                "3. Do not duplicate sections. Do not lose CGPA or metrics.\\n"
                "4. Do not add skills they do not have.\\n"
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
                warnings.append("Tailoring failed/hallucinated. Returning unmodified original.")
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

    if state.get("error"):
        report = f"ANALYSIS FAILED: {state['error']}"
    else:
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
builder.add_node("extract_reqs", extract_and_validate_jd_reqs)
builder.add_node("match_skills", match_skills)
builder.add_node("tailor", tailor_resume)
builder.add_node("report", generate_report)

def check_valid(state: State) -> str:
    return "next" if state.get("is_valid") else "stop"

builder.add_edge(START, "validate_input")
builder.add_conditional_edges("validate_input", check_valid, {"next": "extract_text", "stop": END})
builder.add_conditional_edges("extract_text", check_valid, {"next": "extract_reqs", "stop": END})
builder.add_conditional_edges("extract_reqs", check_valid, {"next": "match_skills", "stop": END})
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
    result = analyzer_graph.invoke(initial_state)
    # Add a fallback status indicator for tests
    result["extraction_status"] = "success" if result.get("requirements") else "failed"
    return result
"""

with open(os.path.join(base, "services", "analyzer.py"), "w") as f:
    f.write(analyzer_service_content)

print("V4 Updates complete.")
