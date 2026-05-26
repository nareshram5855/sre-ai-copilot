import time

import chromadb
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from backend.config import Settings, get_settings
from backend.rag.ingestor import ingest_all
from backend.knowledge.profile_ingest import ingest_profile
from backend.routers._models import IngestResponse

router = APIRouter(prefix="/api/v1", tags=["knowledge"])


@router.post("/ingest", response_model=IngestResponse)
def ingest_async(background_tasks: BackgroundTasks):
    """Trigger ingestion in background. Returns immediately."""
    background_tasks.add_task(ingest_all)
    return {"status": "ingestion_started", "ingested": {}, "duration_seconds": 0.0}


@router.post("/ingest/sync", response_model=IngestResponse)
def ingest_sync():
    """Synchronous ingestion — blocks until complete. Use for initial setup and CI."""
    start = time.time()
    try:
        result = ingest_all()
        return {"status": "complete", "ingested": result, "duration_seconds": round(time.time() - start, 2)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/ingest/profile/sync", response_model=IngestResponse)
def ingest_profile_sync():
    """Synchronous profile ingestion for recruiter RAG."""
    start = time.time()
    try:
        count = ingest_profile(force=True)
        return {
            "status": "complete",
            "ingested": {"profile": count},
            "duration_seconds": round(time.time() - start, 2),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/knowledge/status")
def knowledge_status(cfg: Settings = Depends(get_settings)):
    """
    Returns document count per collection.
    Use this to verify ingestion worked before running triage.
    """
    try:
        client = chromadb.HttpClient(host=cfg.chroma_host, port=cfg.chroma_port)
        counts = {}
        for domain, collection_name in cfg.knowledge_collections.items():
            try:
                counts[domain] = client.get_collection(collection_name).count()
            except Exception:
                counts[domain] = 0
        return {"status": "connected", "collections": counts}
    except Exception as exc:
        return {"status": "disconnected", "error": str(exc), "collections": {}}
