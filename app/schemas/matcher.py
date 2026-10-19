from pydantic import BaseModel, Field
from typing import Literal, TypedDict

# API Request & Response Schemas
class MatchRequest(BaseModel):
    resume_txt: str = Field(..., description="The text content of the resume")
    job_description: str = Field(..., description="The text content of the job description")

class MatchResponse(BaseModel):
    error: str
    report: str
    is_valid: bool
    evidence_valid: bool
    mention_skills: list[str]
    non_mention_skills: list[str]

# Internal LangGraph Schemas
class Requirement(BaseModel):
    skill: str = Field(description="Technology name only, such as PostgreSQL, without 'experience'")
    priority: Literal["required", "preferred", "unspecified", "not_required"]
    evidence: str = Field(description="Exact quote from the job description supporting this requirement")

class ExtractedRequirements(BaseModel):
    requirements: list[Requirement]

class RequirementData(TypedDict):
    skill: str
    priority: Literal["required", "preferred", "unspecified"]
    evidence: str

class State(TypedDict):
    resume_txt: str
    job_description: str
    is_valid: bool
    error: str
    requirements: list[RequirementData]
    mention_skills: list[str]
    non_mention_skills: list[str]
    report: str
    evidence_valid: bool
