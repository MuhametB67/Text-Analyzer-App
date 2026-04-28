from typing import Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from celery import group, chord
from celery.result import AsyncResult, GroupResult

from .celery_app import celery_app
from .tasks import basic_stats, readability, sentiment, keywords, entities, aggregate_analysis

app = FastAPI(title="Text Analyzer")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

MAX_CHARS = 100_000


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text to analyze")


class JobResponse(BaseModel):
    job_id: str
    group_id: str
    total_tasks: int


@app.post("/api/jobs", response_model=JobResponse)
def create_job(req: AnalyzeRequest) -> JobResponse:
    if len(req.text) > MAX_CHARS:
        raise HTTPException(400, f"Text too long ({len(req.text)} chars). Max {MAX_CHARS}.")

    subtasks = [
        basic_stats.s(req.text),
        readability.s(req.text),
        sentiment.s(req.text),
        keywords.s(req.text),
        entities.s(req.text),
    ]

    header = group(subtasks)
    workflow = chord(header)(aggregate_analysis.s())

    group_result: GroupResult = workflow.parent
    group_result.save()

    return JobResponse(
        job_id=workflow.id,
        group_id=group_result.id,
        total_tasks=len(subtasks),
    )


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, group_id: Optional[str] = None) -> dict:
    result = AsyncResult(job_id, app=celery_app)

    payload = {
        "job_id": job_id,
        "status": result.status,
        "ready": result.ready(),
        "successful": result.successful() if result.ready() else None,
        "result": None,
        "progress": None,
    }

    if result.ready():
        if result.successful():
            payload["result"] = result.result
        else:
            payload["result"] = {"error": str(result.result)}

    if group_id:
        group_result = GroupResult.restore(group_id, app=celery_app)
        if group_result is not None:
            total = len(group_result.results)
            completed = group_result.completed_count()
            payload["progress"] = {
                "completed": completed,
                "total": total,
                "percent": round((completed / total) * 100, 1) if total else 0.0,
            }

    return payload


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
