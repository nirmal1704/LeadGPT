from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from api.routes_jobs import router as jobs_router
from api.routes_projects import router as projects_router
from api.routes_exports import router as exports_router
from api.routes_auth import router as auth_router
from api.routes_intake import router as intake_router

app = FastAPI(title="LeadGPT API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs_router)
app.include_router(projects_router)
app.include_router(exports_router)
app.include_router(auth_router)
app.include_router(intake_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
