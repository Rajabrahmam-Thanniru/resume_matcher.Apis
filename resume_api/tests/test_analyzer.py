import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app
from app.services.matching_utils import normalize_skill, find_skill_in_text

client = TestClient(app)

# 1. Test Matching & Aliases
def test_skill_aliases():
    assert normalize_skill("React.js") == "react"
    assert normalize_skill("C#") == "c#"
    assert normalize_skill("DotNet") == ".net"
    assert normalize_skill("Next.js") == "next.js"
    assert normalize_skill("K8s") == "kubernetes"
    
def test_punctuation_sensitive_boundaries():
    text = "We use C++ for backend, C# for tools, and Next.js for frontend."
    assert find_skill_in_text("C#", text) is not None
    assert find_skill_in_text("C++", text) is not None
    assert find_skill_in_text("Next.js", text) is not None
    assert find_skill_in_text(".NET", text) is None
    
    text2 = "I built an app using .NET core and Outlook API."
    assert find_skill_in_text(".NET", text2) is not None
    assert find_skill_in_text("Outlook API", text2) is not None

def test_irrelevant_evidence():
    text = "Collaborate with the team during Agile sprints."
    # Should fail for docker
    assert find_skill_in_text("Docker", text) is None
    assert find_skill_in_text("PostgreSQL", text) is None

# Mocking Ollama for API test
@patch('app.services.analyzer.chat')
def test_analyzer_endpoint(mock_chat):
    # Mocking first call (Requirements Extraction)
    class MockReqMsg:
        content = '''{"requirements": [
            {"skill": "React", "priority": "required", "evidence": "React required."},
            {"skill": "C#", "priority": "required", "evidence": "Need C#."},
            {"skill": "Docker", "priority": "unspecified", "evidence": "Docker containers."}
        ]}'''
    
    # Mocking second call (Tailoring)
    class MockTailorMsg:
        content = '''{
            "sections": [
                {"heading": "Experience", "content": "Did React stuff."}
            ],
            "changes_made": ["Improved clarity."],
            "suggestions": []
        }'''
    
    class MockResponse:
        def __init__(self, msg):
            self.message = msg
            
    mock_chat.side_effect = [MockResponse(MockReqMsg), MockResponse(MockTailorMsg)]
    
    # Needs Auth Cookie
    login_response = client.post("/login", data={"username": "Raja", "password": "r2a8j2a8"})
    assert login_response.status_code == 200
    cookies = login_response.cookies

    # Create dummy PDF
    from fpdf import FPDF
    import os
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="I know React and C# This text is appended to make the document longer than 50 characters to pass the validation check.", ln=True)
    pdf.output("dummy_test.pdf")
    
    with open("dummy_test.pdf", "rb") as f:
        resp = client.post(
            "/api/analyze-resume", 
            files={"resume_pdf": ("dummy_test.pdf", f, "application/pdf")},
            data={"job_description": "React required. Need C#. Docker containers."},
            cookies=cookies
        )
        
    os.remove("dummy_test.pdf")
    
    assert resp.status_code == 200
    data = resp.json()
    assert "react" in data["mention_skills"]
    assert "c#" in data["mention_skills"]
    assert "docker" in data["non_mention_skills"] # Unspecified goes into required
