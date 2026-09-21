# PDS PREDICT — Prototype (K:\DemandSYNC)

Prototype, not demo. See `K:\DemandSYNC\ARCHITECTURE.md` for full design.

## Quick Start (when dataset provided)

```bash
# 1. Drop dataset into data/ or give path
# 2. Ingest
python backend/scripts/ingest_dataset.py --path ..\data\your_file.csv

# 3. Run
docker compose up
# backend: http://localhost:8000/docs
# dashboard: http://localhost:3000
```

## Structure

See ARCHITECTURE.md Sec 7 for build order.
