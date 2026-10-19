# Resume API (`resume_api`)

FastAPI backend application for the Resume Matcher & Tailor system.

> For full architectural details, complete endpoints reference, and LangGraph workflow, see the [Apis Root README](../README.md).

---

## Quick Start

### 1. Prerequisites
- Python 3.10+
- Ollama running locally (`ollama pull qwen2.5:1.5b` and `ollama serve`)

### 2. Activate Environment
```powershell
# If using Conda:
conda activate resume_matcher

# Or if using venv:
..\.venv\Scripts\Activate.ps1
```

### 3. Run the Server
From this directory (`resume_matcher.Apis/resume_api`):

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Interactive API documentation will be available at:
- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- ReDoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## Testing

Run tests with `pytest`:

```powershell
pytest tests/
```

---

## Directory Structure

```text
resume_api/
├── app/
│   ├── main.py            # FastAPI application entry point
│   ├── core/              # Config (Ollama, JWT, paths) and security utilities
│   ├── models/            # Internal data classes & state definitions
│   ├── routers/           # Auth, Analyzer, and Matcher API routes
│   ├── schemas/           # Pydantic request and response schemas
│   └── services/          # LangGraph graph, PDF parsing/export, matching utilities
├── temp_resumes/          # Storage for generated tailored PDFs
└── tests/                 # Comprehensive test scenarios and regression tests
```
