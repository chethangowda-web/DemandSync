# DemandSYNC (PDS PREDICT)

Dataset-driven pre-dispatch demand intelligence layer for the Public Distribution System.
ML predicts -> rules validate -> OR-Tools optimises -> humans authorise -> manifest is hashed -> audit.

## Layout
- `backend/` FastAPI service
- `frontend/officer-web/` React + TS officer portals
- `frontend/beneficiary-mobile/` Flutter beneficiary app
- `database/migrations/` SQL migrations
- `data/` synthetic seed dataset (seed 20260921)
- `docs/` PRD, TRD, architecture, workflow, API contract, RBAC, implementation plan

## Run
```bash
python -m pip install -r backend/requirements-dev.txt
python -m pytest tests -q
python -m uvicorn backend.main:app --reload   # http://localhost:8000/docs
# or: docker compose -f docker/docker-compose.yml up --build
```
Copy `.env.example` to `.env` for configuration.
