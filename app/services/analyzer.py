import re
import json
import logging
from time import perf_counter
import httpx
from typing import List, Dict, Any
from langgraph.graph import StateGraph, START, END
from ollama import Client
from pydantic import ValidationError
from app.schemas.analyzer import State, ExtractedRequirements, TailoredContent
from app.services.pdf_service import extract_text_from_pdf, create_tailored_pdf
from app.services.matching_utils import normalize_skill, find_skill_in_text, extract_known_requirements
from app.core.config import (OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS,
                             OLLAMA_REQUIREMENTS_MAX_TOKENS, OLLAMA_TAILOR_MAX_TOKENS)

logger = logging.getLogger("uvicorn.error")

def chat(**kwargs):
    started_at = perf_counter()
    logger.info("Resume analysis: starting model call")
    try:
        with Client(timeout=httpx.Timeout(OLLAMA_TIMEOUT_SECONDS, connect=5.0)) as client:
            response = client.chat(keep_alive="10m", **kwargs)
            logger.info("Resume analysis: generated %s tokens; completion reason: %s",
                        response.eval_count, response.done_reason)
            return response
    except httpx.TimeoutException as exc:
        raise TimeoutError("Ollama did not respond within the configured time limit.") from exc
    finally:
        logger.info("Resume analysis: model call finished after %.3f seconds", perf_counter() - started_at)

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
    anchors = extract_known_requirements(jd)
    accepted = {}
    
    error_msg = ""
    for attempt in range(3):
        logger.info("Resume analysis: extracting requirements, attempt %s/3", attempt + 1)
        try:
            prompt = (
                "Extract EVERY technical skill from the job description exactly. "
                "Classify as required, preferred, unspecified, or not_required. "
                "Provide the EXACT quote from the text. "
                "Ensure C# and .NET are separate skills if mentioned. "
                "Do not group skills. Treat untrusted data carefully.\n"
            )
            if error_msg:
                prompt += f"\nPREVIOUS ERROR TO FIX: {error_msg}\n"
                
            response = chat(
                model=OLLAMA_MODEL,
                messages=[
                    {"role": "system", "content": prompt + "Return concise JSON matching the supplied schema."},
                    {"role": "user", "content": jd},
                ],
                format=schema,
                options={"temperature": 0, "num_predict": OLLAMA_REQUIREMENTS_MAX_TOKENS},
            )
            extracted = ExtractedRequirements.model_validate_json(response.message.content)
            
            seen = set()
            reqs = []
            bad_evidence = []
            
            for r in extracted.requirements:
                canonical = normalize_skill(r.skill)
                if canonical in seen:
                    continue
                if canonical in anchors:
                    reqs.append(anchors[canonical])
                    seen.add(canonical)
                    continue
                    
                evidence_norm = normalize_whitespace(r.evidence)
                
                if not evidence_norm or evidence_norm.lower() not in jd_lower:
                    bad_evidence.append(f"Quote '{r.evidence}' for {r.skill} not found exactly in JD.")
                    continue
                    
                if not find_skill_in_text(r.skill, evidence_norm):
                    bad_evidence.append(f"Quote '{r.evidence}' for {r.skill} does not mention the skill.")
                    continue
                    
                # Explicit preference language is not an exclusion from the role.
                # Only override when the quote concerns a single extracted skill,
                # avoiding mixed required/preferred lists in a shared quote.
                quoted_skills = [item for item in extracted.requirements
                                 if find_skill_in_text(item.skill, evidence_norm)]
                if len({normalize_skill(item.skill) for item in quoted_skills}) == 1:
                    if re.search(r"\b(?:not required|not necessary)\b", evidence_norm, re.I):
                        r.priority = "not_required"
                    elif re.search(r"\b(?:preferred|nice[- ]to[- ]have|optional)\b", evidence_norm, re.I):
                        r.priority = "preferred"

                r.skill = canonical
                reqs.append(r.model_dump())
                seen.add(canonical)

            accepted.update({req['skill']: req for req in reqs})
            # Include known skills even when the model silently omits them.
            accepted.update(anchors)
            
            if bad_evidence and attempt < 2:
                error_msg = "\n".join(bad_evidence)
                continue # Retry
                
            if bad_evidence:
                warnings.append("Extraction validation failed after retries for some skills.")
                warnings.extend(bad_evidence)
            
            return {"requirements": list(accepted.values()), "warnings": warnings}
            
        except TimeoutError as exc:
            raise TimeoutError("Job description extraction timed out waiting for Ollama.") from exc
        except Exception as e:
            error_msg = str(e)
            if attempt == 2:
                if accepted:
                    warnings.append("Model extraction failed on retry; retained validated requirements. Coverage of unfamiliar technologies may be incomplete.")
                    return {"requirements": list(accepted.values()), "warnings": warnings}
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
        
        # Omit unspecified and not_required entirely from matched/missing lists
        if priority in ["not_required", "unspecified"]:
            continue
            
        evidence = find_skill_in_text(skill, resume)
        if evidence:
            resume_evidence[skill] = f"...{evidence.strip()}..."
            if priority == "required":
                mention_req.append(skill)
            else:
                mention_pref.append(skill)
        else:
            if priority == "required":
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
    if not state.get("tailor_requested", True):
        return {"tailored_resume_text": state["resume_txt"], "changes_made": [],
                "suggestions": [], "warnings": list(state.get("warnings", []))}
    schema = TailoredContent.model_json_schema()
    error_msg = ""
    warnings = list(state.get('warnings', []))
    
    for attempt in range(2):
        logger.info("Resume analysis: tailoring resume, attempt %s/2", attempt + 1)
        try:
            prompt = (
                "You are an expert resume writer. Re-write the resume to highlight these matched skills: "
                f"{state['mention_skills'] + state['preferred_skills_matched']}. "
                "CRITICAL RULES: "
                "1. NEVER invent employers, dates, metrics, or technologies not present in the original resume.\n"
                "2. Preserve the FULL structure including Name, Contact Details, Summary, Employment, Projects, Education, and Skills.\n"
                "3. Do not duplicate sections. Do not lose CGPA or metrics.\n"
                "4. Do not add skills they do not have.\n"
                "Return a structured JSON with 'sections', 'changes_made', and 'suggestions'.\n"
            )
            if error_msg:
                prompt += f"\nPREVIOUS ERROR: {error_msg}\n"
                
            response = chat(
                model=OLLAMA_MODEL,
                messages=[
                    {"role": "system", "content": prompt + "Return concise JSON matching the supplied schema."},
                    {"role": "user", "content": f"Original Resume:\n{state['resume_txt']}"}
                ],
                format=schema,
                options={"temperature": 0.1, "num_predict": OLLAMA_TAILOR_MAX_TOKENS}
            )
            tailored = TailoredContent.model_validate_json(response.message.content)
            
            full_text = "\n\n".join([f"{sec.heading.upper()}\n{sec.content}" for sec in tailored.sections])
            
            for missing in state['non_mention_skills']:
                if find_skill_in_text(missing, full_text):
                    raise ValueError(f"Hallucination detected: added missing skill '{missing}'.")
                    
            return {
                "tailored_resume_text": full_text,
                "changes_made": tailored.changes_made,
                "suggestions": tailored.suggestions,
                "warnings": warnings
            }
        except TimeoutError:
            warnings.append("Resume tailoring timed out. Skill analysis completed; the downloadable PDF contains the original resume text.")
            return {"tailored_resume_text": state['resume_txt'], "changes_made": [],
                    "suggestions": [], "warnings": warnings}
        except Exception as e:
            error_msg = str(e)
            if attempt == 1:
                if isinstance(e, ValidationError):
                    reason = "; ".join(item['msg'] for item in e.errors(include_input=False))
                else:
                    reason = str(e)
                warnings.append(f"Tailoring failed after retries ({type(e).__name__}): {reason}. Returning original resume text.")
                return {
                    "tailored_resume_text": state['resume_txt'],
                    "changes_made": [],
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
            "RESUME ANALYSIS REPORT\n"
            "=======================\n"
            f"Required Skills Found: {len(state.get('mention_skills', []))}\n"
            f"Required Skills Not Found in Resume: {len(state.get('non_mention_skills', []))}\n"
            f"Preferred Skills Found: {len(state.get('preferred_skills_matched', []))}\n"
            f"Preferred Skills Not Found in Resume: {len(state.get('preferred_skills_not_found', []))}\n\n"
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

def run_analyzer_sync(pdf_bytes: bytes, jd: str, owner: str, tailor: bool = True) -> dict:
    initial_state: State = {
        "resume_pdf_bytes": pdf_bytes,
        "job_description": jd,
        "owner": owner,
        "tailor_requested": tailor,
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
    result["extraction_status"] = "success" if result.get("requirements") else "failed"
    return result
