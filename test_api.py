import requests
from fpdf import FPDF
import os

BASE_URL = "http://127.0.0.1:8000"

# 1. Create a dummy PDF resume for testing
print("1. Creating a dummy resume PDF...")
pdf = FPDF()
pdf.add_page()
pdf.set_font("Arial", size=12)
pdf.cell(200, 10, txt="Raja's Resume", ln=True)
pdf.cell(200, 10, txt="I am a software engineer with 5 years of experience in Python and FastAPI.", ln=True)
pdf.cell(200, 10, txt="I also have experience with PostgreSQL databases and Docker.", ln=True)
pdf.output("dummy_resume.pdf")

# 2. Log in to get the authentication cookie
print("2. Logging in...")
login_data = {"username": "Raja", "password": "r2a8j2a8"}
session = requests.Session()
try:
    login_response = session.post(f"{BASE_URL}/login", data=login_data)
    if login_response.status_code == 200:
        print("   ✅ Login successful!")
    else:
        print("   ❌ Login failed! Is the server running?")
        exit()
except Exception as e:
    print("   ❌ Connection failed! Make sure you started the server with: uvicorn app.main:app")
    exit()

# 3. Test the Analyzer API
print("3. Uploading to AI Analyzer (This takes 10-30 seconds depending on Ollama)...")
jd = "We are looking for a backend developer. Required skills: Python, FastAPI, and PostgreSQL. Preferred: React."

with open("dummy_resume.pdf", "rb") as f:
    files = {"resume_pdf": ("dummy_resume.pdf", f, "application/pdf")}
    data = {"job_description": jd}
    
    response = session.post(f"{BASE_URL}/api/analyze-resume", files=files, data=data)
    
    if response.status_code == 200:
        result = response.json()
        print("\n=== AI ANALYSIS REPORT ===")
        print(result["report"])
        print("\nRequired Skills Found:", result["mention_skills"])
        print("Required Skills Missing:", result["non_mention_skills"])
        print("Preferred Skills Missing:", result["preferred_skills_not_found"])
        
        # 4. Download the tailored PDF
        download_id = result.get("download_id")
        if download_id:
            print(f"\n4. Downloading tailored resume (ID: {download_id})...")
            pdf_response = session.get(f"{BASE_URL}/api/download-resume/{download_id}")
            with open("tailored_downloaded.pdf", "wb") as out_f:
                out_f.write(pdf_response.content)
            print("   ✅ Downloaded successfully as 'tailored_downloaded.pdf'")
    else:
        print("   ❌ Analysis failed:", response.text)

# Cleanup original dummy file
if os.path.exists("dummy_resume.pdf"):
    os.remove("dummy_resume.pdf")
