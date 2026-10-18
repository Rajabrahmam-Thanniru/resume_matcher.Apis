from pydantic import BaseModel, Field
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
    response_time_seconds: float = Field(
        default=0.0, ge=0,
        description="Server processing time in seconds, including file reading and analysis; excludes network transfer and authentication."
    )
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
    tailor_requested: bool
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
