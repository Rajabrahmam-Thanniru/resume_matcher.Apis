from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.matcher import MatchRequest, MatchResponse
from app.services.matcher import run_matcher
from app.core.security import get_current_user_from_cookie

router = APIRouter()

@router.post("/match", response_model=MatchResponse)
def match_resume(
    request: MatchRequest, 
    username: str = Depends(get_current_user_from_cookie)
):
    """
    Takes a resume and a job description, runs them through the LangGraph AI flow, 
    and returns the skill comparison report. 
    (Requires authentication via login cookie).
    """
    try:
        result = run_matcher(request.resume_txt, request.job_description)
        
        # If the graph ended early due to validation errors
        if result.get("error"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=result["error"]
            )
            
        return MatchResponse(
            error=result.get("error", ""),
            report=result.get("report", ""),
            is_valid=result.get("is_valid", False),
            evidence_valid=result.get("evidence_valid", False),
            mention_skills=result.get("mention_skills", []),
            non_mention_skills=result.get("non_mention_skills", [])
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
