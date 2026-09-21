"""
DemandSYNC — FastAPI Entry (Phase 0 Foundation)
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="DemandSYNC API", version="0.1.0-phase0", description="PDS PREDICT — AI-powered PDS intelligence layer — Phase 0 Auth Foundation")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

from backend.api.beneficiary import router as beneficiary_router
from backend.api.auth import router as auth_router
app.include_router(beneficiary_router)
app.include_router(auth_router)

@app.get("/health")
def health(): return {"status":"ok","phase":"1-beneficiary","db":"PostgreSQL+PostGIS","datasets":"83,763 rows validated"}

@app.get("/api/v1/datasets/manifest")
def dataset_manifest():
    import json
    from backend.core.config import DATA_DIR
    p = DATA_DIR / "07_generated" / "dataset_manifest.json"
    return json.loads(p.read_text()) if p.exists() else {"error":"manifest not found"}

# Routers will be included per phase:
# Phase 1: from api.datasets import router
# Phase 2: from api.cycles import router
# ...

if __name__=="__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
