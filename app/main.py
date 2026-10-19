from fastapi import FastAPI
from app.routers import auth, matcher, analyzer

app = FastAPI(title="Resume API (v2)")

app.include_router(auth.router, tags=["Authentication"])
app.include_router(matcher.router, prefix="/api", tags=["Legacy Text Matcher"])
app.include_router(analyzer.router, prefix="/api", tags=["Advanced PDF Analyzer"])

@app.get("/")
def home():
    return {"message": 'oii server is up and running mr K'}
