"""
Prototype dataset ingestion — expects REAL dataset (CSV/Excel/JSON), not demo.
Usage: python ingest_dataset.py --path data/your_file.csv
Validates schema, loads into PostgreSQL.
TODO: wire DATABASE_URL from env, use pandas + sqlalchemy.
"""
import argparse, pathlib, sys
parser = argparse.ArgumentParser()
parser.add_argument("--path", required=True, help="Path to dataset file")
args = parser.parse_args()
p = pathlib.Path(args.path)
if not p.exists():
    print(f"ERROR: file not found: {p}")
    sys.exit(1)
print(f"[ingest] Found {p} ({p.stat().st_size} bytes)")
print("[ingest] Schema validation: beneficiaries, fps, warehouses, vehicles, historical_demand, allocations")
print("[ingest] TODO: implement real ingestion when dataset provided — currently scaffold only, no demo data inserted")
