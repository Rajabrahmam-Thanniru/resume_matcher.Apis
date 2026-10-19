# Resume Tailor & Analyzer API (`resume_matcher.Apis`)

A high-performance FastAPI service powered by LangGraph and Ollama for extracting job requirements, evaluating resume coverage, performing factual tailoring, and generating updated PDF resumes.

---

## Overview

The backend service provides:
- **Intelligent Job Parsing**: Extracts required and preferred skills along with verbatim supporting quotes from job descriptions.
- **Evidence Verification**: Validates extracted quotes against original job descriptions to prevent hallucinated requirements.
- **Factual Resume Tailoring**: Re-emphasizes genuine candidate achievements matching job criteria without inventing unverified experience.
- **Automated PDF Generation**: Converts tailored text into downloadable PDF resumes using FPDF2 with Unicode font support.
- **Secure Cookie Authentication**: HttpOnly JWT access and refresh token management.
- **Legacy Text Matcher**: Fallback text-based matching endpoint for rapid comparisons.

---

## Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) with [Uvicorn](https://www.uvicorn.org/)
- **AI / LLM Orchestration**: [LangGraph](https://langchain-ai.github.io/langgraph/) + [LangChain](https://www.langchain.com/)
- **LLM Runtime**: [Ollama](https://ollama.ai/) (default model: `qwen2.5:1.5b`)
- **PDF Processing**: [pypdf](https://pypdf.readthedocs.io/) (text extraction) & [fpdf2](https://py-pdf.github.io/fpdf2/) (PDF generation)
- **Security & Tokens**: [PyJWT](https://pyjwt.readthedocs.io/) with HttpOnly Cookies
- **Validation**: [Pydantic v2](https://docs.pydantic.dev/latest/)
- **Testing**: [pytest](https://docs.pytest.org/) with asynchronous test support

---

## Project Structure

```text
resume_matcher.Apis/
├── requirements.txt              # Production and development pip dependencies
├── environment.yml               # Conda environment definition
├── resume_api/                   # Main backend application package
│   ├── app/
│   │   ├── main.py               # FastAPI entry point & router aggregation
│   │   ├── core/
│   │   │   ├── config.py         # App configuration & environment variables
│   │   │   └── security.py       # JWT creation, cookie verification, auth helpers
│   │   ├── models/               # Internal data and state structures
│   │   ├── routers/
│   │   │   ├── analyzer.py       # PDF analysis, tailoring & PDF download endpoints
│   │   │   ├── auth.py           # Login, refresh, logout & protected check
│   │   │   └── matcher.py        # Legacy plain-text matcher endpoint
│   │   ├── schemas/              # Pydantic request & response models
│   │   └── services/
│   │       ├── analyzer.py       # LangGraph resume analysis & tailoring pipeline
│   │       ├── matcher.py        # Plain-text matching pipeline
│   │       ├── matching_utils.py # Skill comparison and evidence helpers
│   │       └── pdf_service.py    # PDF text extraction and PDF creation
│   ├── temp_resumes/             # Transient storage for generated tailored PDFs
│   ├── tests/                    # Pytest test suite (scenarios, regressions, v4)
│   └── README.md                 # Package-level documentation
```

---

## Getting Started

### Prerequisites

1. **Python 3.10+** (via Conda, venv, or system Python)
2. **Ollama**: Download and install from [ollama.ai](https://ollama.ai/)

### 1. Install & Start Ollama

Ensure Ollama is running and pull the default model:

```powershell
ollama pull qwen2.5:1.5b
ollama serve
```

> [!TIP]
> You can substitute other Ollama models (e.g. `llama3.2`, `mistral`) by changing the `OLLAMA_MODEL` environment variable.

### 2. Environment Setup & Dependency Installation

#### Option A: Using Conda (Recommended)

```powershell
conda env create -f environment.yml
conda activate resume_matcher
```

#### Option B: Using Python Virtual Environment (`venv`)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Environment Variables

Configure the following environment variables if needed (defaults shown below):

| Variable | Default | Description |
| --- | --- | --- |
| `SECRET_KEY` | `your-secret-key-keep-it-secret` | Cryptographic key for signing JWT tokens |
| `OLLAMA_MODEL` | `qwen2.5:1.5b` | Ollama model identifier |
| `OLLAMA_TIMEOUT_SECONDS` | `120` | Timeout per Ollama LLM call |
| `ANALYSIS_TIMEOUT_SECONDS` | `300` | Global timeout for entire resume analysis |
| `OLLAMA_REQUIREMENTS_MAX_TOKENS` | `2048` | Max token budget for requirement extraction |
| `OLLAMA_TAILOR_MAX_TOKENS` | `3072` | Max token budget for resume tailoring |

### 4. Run the API Server

From the `resume_matcher.Apis/resume_api` directory:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Verify the server is running by visiting [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for the interactive Swagger documentation.

---

## API Endpoints Reference

### Authentication

> **Default Mock Credentials**: Username `Raja` / Password `r2a8j2a8`

| Method | Endpoint | Description | Request Format | Response / Cookies |
| --- | --- | --- | --- | --- |
| `POST` | `/login` | Authenticate user | `OAuth2PasswordRequestForm` (`username`, `password`) | Sets HttpOnly `access_token` and `refresh_token` cookies |
| `POST` | `/refresh` | Refresh access token | Reads `refresh_token` cookie | Issues updated `access_token` cookie |
| `POST` | `/logout` | Invalidate session | None | Clears authentication cookies |
| `GET` | `/protected` | Session check | Reads `access_token` cookie | Returns username confirmation |

### Advanced PDF Analyzer & Tailoring

| Method | Endpoint | Description | Request Format |
| --- | --- | --- | --- |
| `POST` | `/api/analyze-resume` | Full PDF analysis & tailoring | `multipart/form-data`: `resume_pdf` (PDF file, <=10MB), `job_description` (str), `tailor` (bool, default `true`). Requires auth cookie. |
| `GET` | `/api/download-resume/{file_id}` | Download generated tailored PDF | Path parameter `file_id` (UUID). Requires auth cookie matching file owner. |

### Legacy Matcher

| Method | Endpoint | Description | Request Format |
| --- | --- | --- | --- |
| `POST` | `/api/match` | Plain-text matching | `application/json`: `{ "resume_txt": "...", "job_description": "..." }`. Requires auth cookie. |

---

## AI Analysis Pipeline (LangGraph)

The core analysis in `app/services/analyzer.py` executes a multi-step graph:

```text
[Input PDF & JD] 
       │
       ▼
 1. Extract Text from PDF (pypdf)
       │
       ▼
 2. Extract Requirements (Ollama structured output: skill, priority, exact JD quote)
       │
       ▼
 3. Validate Evidence (Verifies that extracted quotes actually exist in JD)
       │
       ▼
 4. Match Skills (Compares required and preferred skills against resume text)
       │
       ▼
 5. Tailor Resume (Optional: Grounded rewrite to foreground matching skills)
       │
       ▼
 6. Compile PDF (FPDF2 generates downloadable PDF if tailored)
```

---

## Testing

Run the automated test suite from `resume_matcher.Apis/resume_api`:

```powershell
pytest tests/
```

Run specific test suites:

```powershell
# Comprehensive scenario tests
pytest tests/test_comprehensive_scenarios.py

# Regression tests
pytest tests/test_response_regressions.py

# Analyzer unit tests
pytest tests/test_analyzer.py
```

---

## Important Architecture & Security Notes

- **CORS Configuration**: By default, no wildcard CORS middleware is enabled. During local development, the frontend proxy forwards requests seamlessly. When deploying across domains, configure explicit CORS origins with `allow_credentials=True`.
- **Authentication Store**: The current version uses an in-memory dictionary for mock users. Production deployments should connect this to a persistent database (PostgreSQL, SQLite, etc.).
- **PDF Storage & Ownership**: Generated PDFs are saved temporarily in `resume_api/temp_resumes/` and mapped to the requesting user in memory. File access is strictly restricted to the user who requested the analysis.
- **PDF Constraints**: Requires selectable text-based PDFs (up to 10 MB). Scanned image PDFs without an OCR text layer will return a validation error.
