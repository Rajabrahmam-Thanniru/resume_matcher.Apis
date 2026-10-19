import pytest
from unittest.mock import patch, MagicMock
from app.services.analyzer import run_analyzer_sync
from app.services.pdf_service import create_tailored_pdf

# 1. Test PDF Rendering (Horizontal Space Fix)
def test_pdf_rendering_long_word():
    long_word = "A" * 500
    try:
        file_id = create_tailored_pdf(f"Short line\\n{long_word}\\nAnother line", "test_user")
        assert file_id is not None
    except Exception as e:
        pytest.fail(f"PDF generation failed: {str(e)}")

# 2. Test JD Extraction Loop (Mocked)
@patch('app.services.analyzer.chat')
def test_regression_jd_extraction(mock_chat):
    class MockResponse:
        def __init__(self, msg):
            self.message = msg
            
    class MockMsg:
        def __init__(self, c):
            self.content = c

    # First attempt: Invalid evidence (hallucinated quote) and missed skills
    attempt_1 = '''{"requirements": [
        {"skill": "React", "priority": "required", "evidence": "Fake quote."},
        {"skill": "PostgreSQL", "priority": "required", "evidence": "Collaborate with the team during Agile sprints."},
        {"skill": "GraphQL", "priority": "preferred", "evidence": "GraphQL is used by a separate team."}
    ]}'''
    
    # Second attempt: Correct evidence, correctly classifies GraphQL as unspecified, Flutter as not_required.
    attempt_2 = '''{"requirements": [
        {"skill": "React", "priority": "required", "evidence": "React required."},
        {"skill": "TypeScript", "priority": "required", "evidence": "TypeScript required."},
        {"skill": "Node.js", "priority": "required", "evidence": "Node.js required."},
        {"skill": ".NET", "priority": "required", "evidence": ".NET required."},
        {"skill": "C#", "priority": "required", "evidence": "C# required."},
        {"skill": "MongoDB", "priority": "required", "evidence": "MongoDB required."},
        {"skill": "REST APIs", "priority": "required", "evidence": "REST APIs required."},
        {"skill": "JWT", "priority": "required", "evidence": "JWT required."},
        {"skill": "Jest", "priority": "required", "evidence": "Jest required."},
        {"skill": "Docker", "priority": "required", "evidence": "Docker required."},
        {"skill": "PostgreSQL", "priority": "required", "evidence": "PostgreSQL required."},
        {"skill": "Next.js", "priority": "preferred", "evidence": "Next.js preferred."},
        {"skill": "Firebase", "priority": "preferred", "evidence": "Firebase preferred."},
        {"skill": "Firestore", "priority": "preferred", "evidence": "Firestore preferred."},
        {"skill": "Gmail API", "priority": "preferred", "evidence": "Gmail API preferred."},
        {"skill": "Outlook API", "priority": "preferred", "evidence": "Outlook API preferred."},
        {"skill": "Redux", "priority": "preferred", "evidence": "Redux preferred."},
        {"skill": "Redis", "priority": "preferred", "evidence": "Redis preferred."},
        {"skill": "Kubernetes", "priority": "preferred", "evidence": "Kubernetes preferred."},
        {"skill": "GraphQL", "priority": "unspecified", "evidence": "GraphQL is used by a separate team."},
        {"skill": "Flutter", "priority": "not_required", "evidence": "Flutter is not required."}
    ]}'''
    
    # Mocking Tailoring
    tailor_attempt = '''{
        "sections": [
            {"heading": "Contact Details", "content": "Raja | raja@test.com"},
            {"heading": "Experience", "content": "Used React, Node.js, C#, .NET."}
        ],
        "changes_made": ["Highlighted React experience."],
        "suggestions": []
    }'''
    
    mock_chat.side_effect = [
        MockResponse(MockMsg(attempt_1)), 
        MockResponse(MockMsg(attempt_2)), 
        MockResponse(MockMsg(tailor_attempt))
    ]
    
    from fpdf import FPDF
    import os
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    # Put exactly 10 required skills, 6 preferred skills. Omit PostgreSQL, Redis, Kubernetes entirely.
    pdf_text = (
        "My name is Raja. I know React, TypeScript, Node.js, .NET, C#, MongoDB, "
        "REST APIs, JWT, Jest, Docker. I also know Next.js, Firebase, Firestore, "
        "Gmail API, Outlook API, Redux. "
        "I have a CGPA of 3.8."
    )
    pdf.multi_cell(0, 10, text=pdf_text)
    pdf.output("regression_test.pdf")
    
    jd_text = (
        "React required. TypeScript required. Node.js required. .NET required. C# required. "
        "MongoDB required. REST APIs required. JWT required. Jest required. Docker required. "
        "PostgreSQL required. Next.js preferred. Firebase preferred. Firestore preferred. "
        "Gmail API preferred. Outlook API preferred. Redux preferred. Redis preferred. "
        "Kubernetes preferred. GraphQL is used by a separate team. Flutter is not required."
    )
    
    with open("regression_test.pdf", "rb") as f:
        pdf_bytes = f.read()
        
    os.remove("regression_test.pdf")
    
    result = run_analyzer_sync(pdf_bytes, jd_text, "test_user")
    
    assert len(result["mention_skills"]) == 10, f"Expected 10 required, got {result['mention_skills']}"
    assert result["non_mention_skills"] == ["postgresql"]
    assert len(result["preferred_skills_matched"]) == 6
    assert set(result["preferred_skills_not_found"]) == {"redis", "kubernetes"}
    
    assert result.get("extraction_status") == "success"
    assert "CGPA" not in result["changes_made"][0]
