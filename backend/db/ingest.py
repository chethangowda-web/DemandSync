"""Dataset ingestion: validate -> preview -> commit.

Nothing is written unless every check passes. Validation is driven by the database catalog
(column types, nullability, foreign keys), plus explicit business rules, so the checks cannot
drift from the schema. Every real run is recorded in dataset_imports (IMPORTED / ACTIVE /
REJECTED), with the full validation report and a checksum of the input files.

Usage:
  python -m backend.db.ingest --dry-run
  python -m backend.db.ingest --activate
  python -m backend.db.ingest --replace --activate   # dev only: wipes dataset tables first
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import psycopg

from backend.core.config import DATA_DIR
from backend.db.conn import connect

# (table, csv path relative to the data dir, primary key columns) in FK-dependency order
DATASETS: list[tuple[str, str, list[str]]] = [
    ("officers", "01_master/officers_master.csv", ["officer_id"]),
    ("warehouses", "01_master/warehouse_master.csv", ["warehouse_id"]),
    ("fps", "01_master/fps_master.csv", ["fps_id"]),
    ("vehicles", "01_master/vehicle_fleet.csv", ["vehicle_id"]),
    ("beneficiaries", "01_master/beneficiaries_master.csv", ["beneficiary_id"]),
    ("historical_demand", "02_demand/historical_demand.csv", ["fps_id", "cycle", "commodity"]),
    ("intent_signals", "02_demand/intent_signals.csv", ["intent_id"]),
    ("demand_forecast", "02_demand/demand_forecast.csv", ["forecast_id"]),
    ("allocations", "02_demand/allocations.csv", ["allocation_id"]),
    ("dispatch_manifests", "03_operations/dispatch_manifests.csv", ["manifest_id"]),
    ("dispatch_manifest_items", "03_operations/dispatch_manifest_items.csv", ["manifest_item_id"]),
    ("delivery_history", "03_operations/delivery_history.csv", ["delivery_id"]),
    ("epos_transactions", "03_operations/epos_transactions.csv", ["transaction_id"]),
    ("inventory", "03_operations/inventory.csv", ["inventory_id"]),
    ("vehicle_routes", "04_tracking/vehicle_routes.csv", ["route_id"]),
    ("vehicle_telemetry", "04_tracking/vehicle_telemetry.csv", ["telemetry_id"]),
    ("inspections", "05_compliance/inspections.csv", ["inspection_id"]),
    ("grievances", "05_compliance/grievances.csv", ["grievance_id"]),
    ("audit_events", "05_compliance/audit_events.csv", ["audit_event_id"]),
    ("exceptions", "05_compliance/exceptions.csv", ["exception_id"]),
    ("weather", "06_context/weather.csv", ["date", "district"]),
    ("calendar_events", "06_context/calendar_events.csv", ["date", "district", "event_name"]),
    ("historical_stockouts", "06_context/historical_stockouts.csv", ["fps_id", "cycle", "commodity"]),
]
TABLES = [t for t, _, _ in DATASETS]
_NUMERIC = {"numeric", "integer", "bigint", "smallint", "double precision"}
_TEMPORAL = {"date", "timestamp with time zone", "timestamp without time zone"}
_LOCKED_STATES = ("LOCKED", "DISPATCHED", "DELIVERED", "RECONCILED")


@dataclass
class Check:
    dataset: str
    level: str  # schema | type | key | referential | business
    name: str
    status: str  # PASS | FAIL
    failed_rows: int = 0
    details: str = ""


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)

    def add(self, dataset: str, level: str, name: str, failed: int = 0, details: str = "") -> None:
        self.checks.append(Check(dataset, level, name, "FAIL" if failed else "PASS", failed, details))

    @property
    def ok(self) -> bool:
        return all(c.status == "PASS" for c in self.checks)

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if c.status == "FAIL"]

    def to_json(self) -> dict:
        return {
            "passed": self.ok,
            "total": len(self.checks),
            "failed": len(self.failures),
            "checks": [asdict(c) for c in self.checks],
        }


class ImportBlocked(RuntimeError):
    """Raised when the target database already holds dataset rows and --replace was not given."""


# --------------------------------------------------------------------------- loading

def load_frames(data_dir: Path, report: Report) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for table, rel, _ in DATASETS:
        path = data_dir / rel
        if not path.exists():
            report.add(table, "schema", "file_exists", 1, f"missing file {rel}")
            continue
        try:
            df = pd.read_csv(path, dtype=str, keep_default_na=False)
        except Exception as e:  # malformed CSV
            report.add(table, "schema", "file_parses", 1, f"{rel}: {e}")
            continue
        report.add(table, "schema", "file_exists")
        frames[table] = df
    return frames


def dataset_checksum(data_dir: Path) -> str:
    h = hashlib.sha256()
    for _, rel, _ in DATASETS:
        p = data_dir / rel
        if p.exists():
            h.update(rel.encode())
            h.update(p.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce")


# --------------------------------------------------------------------------- catalog-driven checks

def _catalog(conn: psycopg.Connection):
    cols: dict[str, dict[str, dict]] = {}
    for t, c, dt, nullable, default in conn.execute(
        """SELECT table_name, column_name, data_type, is_nullable, column_default
           FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = ANY(%s)
           ORDER BY table_name, ordinal_position""",
        (TABLES + ["cycles"],),
    ):
        cols.setdefault(t, {})[c] = {"type": dt, "nullable": nullable == "YES", "default": default}
    fks = conn.execute(
        """SELECT c.conrelid::regclass::text, a.attname, c.confrelid::regclass::text, af.attname
           FROM pg_constraint c
           JOIN pg_attribute a  ON a.attrelid = c.conrelid  AND a.attnum  = c.conkey[1]
           JOIN pg_attribute af ON af.attrelid = c.confrelid AND af.attnum = c.confkey[1]
           WHERE c.contype = 'f' AND c.connamespace = 'public'::regnamespace
             AND array_length(c.conkey, 1) = 1 AND c.conrelid::regclass::text = ANY(%s)""",
        (TABLES,),
    ).fetchall()
    return cols, fks


def _sample(values: pd.Series, n: int = 3) -> str:
    return ", ".join(repr(v) for v in values.head(n).tolist())


def check_schema_and_types(report: Report, frames, cols) -> None:
    for table, df in frames.items():
        tcols = cols.get(table, {})
        extra = [c for c in df.columns if c not in tcols]
        missing = [c for c, m in tcols.items() if c not in df.columns and not m["nullable"] and m["default"] is None]
        report.add(table, "schema", "no_unknown_columns", len(extra), f"unknown: {extra}" if extra else "")
        report.add(table, "schema", "required_columns_present", len(missing), f"missing: {missing}" if missing else "")
        report.add(table, "schema", "not_empty", 0 if len(df) else 1, "no rows" if not len(df) else "")
        for c in df.columns:
            if c not in tcols:
                continue
            meta, s = tcols[c], df[c]
            blank = s.str.strip() == ""
            if not meta["nullable"] and meta["default"] is None:
                n = int(blank.sum())
                report.add(table, "type", f"{c}_not_null", n, f"e.g. rows {list(df.index[blank][:3] + 2)}" if n else "")
            filled = ~blank
            if meta["type"] in _NUMERIC:
                bad = filled & pd.to_numeric(s, errors="coerce").isna()
                report.add(table, "type", f"{c}_numeric", int(bad.sum()), _sample(s[bad]) if bad.any() else "")
                num = pd.to_numeric(s, errors="coerce")
                if c.endswith("_kg") and "variance" not in c:  # quantities can never be negative
                    neg = filled & (num < 0)
                    report.add(table, "business", f"{c}_not_negative", int(neg.sum()), _sample(s[neg]) if neg.any() else "")
                if c in ("latitude", "longitude"):
                    lim = 90 if c == "latitude" else 180
                    out = filled & (num.abs() > lim)
                    report.add(table, "business", f"{c}_in_range", int(out.sum()), _sample(s[out]) if out.any() else "")
            elif meta["type"] in _TEMPORAL:
                bad = filled & pd.to_datetime(s, errors="coerce", format="mixed").isna()
                report.add(table, "type", f"{c}_datetime", int(bad.sum()), _sample(s[bad]) if bad.any() else "")


def check_keys(report: Report, frames) -> None:
    for table, _, pk in DATASETS:
        if table in frames and all(c in frames[table].columns for c in pk):
            dup = int(frames[table].duplicated(subset=pk).sum())
            report.add(table, "key", f"primary_key_unique({','.join(pk)})", dup, "duplicate keys" if dup else "")


def check_references(report: Report, frames, fks, conn) -> None:
    def parent_values(parent: str, col: str) -> set[str]:
        if parent in frames and col in frames[parent].columns:
            return set(frames[parent][col])
        return {r[0] for r in conn.execute(f'SELECT "{col}"::text FROM {parent}')}

    for child, ccol, parent, pcol in fks:
        if child not in frames or ccol not in frames[child].columns:
            continue
        vals = frames[child][ccol]
        vals = vals[vals.str.strip() != ""]  # NULL FKs are allowed where the column is nullable
        orphans = vals[~vals.isin(parent_values(parent, pcol))]
        report.add(child, "referential", f"{ccol}->{parent}.{pcol}", len(orphans),
                   f"orphans e.g. {_sample(orphans.drop_duplicates())}" if len(orphans) else "")


# --------------------------------------------------------------------------- business rules

def check_business(report: Report, frames, data_dir: Path) -> None:
    f = frames

    def rule(dataset: str, name: str, bad: pd.Series, detail: str = "") -> None:
        report.add(dataset, "business", name, int(bad.sum()), detail if bad.any() else "")

    if "beneficiaries" in f:
        b = f["beneficiaries"]
        rule("beneficiaries", "entitlement_equals_rice_plus_wheat",
             _num(b, "entitlement_kg") != _num(b, "rice_entitlement_kg") + _num(b, "wheat_entitlement_kg"))
        rule("beneficiaries", "entitlement_positive", ~(_num(b, "entitlement_kg") > 0), "NFSA entitlement must be > 0")

    if "intent_signals" in f:
        i = f["intent_signals"]
        rule("intent_signals", "total_equals_rice_plus_wheat",
             _num(i, "total_quantity_kg") != _num(i, "rice_quantity_kg") + _num(i, "wheat_quantity_kg"))
        live = i[i["status"] == "SUBMITTED"]
        dup = live.duplicated(subset=["beneficiary_id", "cycle"], keep=False)
        rule("intent_signals", "one_live_intent_per_beneficiary_cycle", dup, "duplicate beneficiary+cycle")
        if "beneficiaries" in f:
            m = live.merge(f["beneficiaries"][["beneficiary_id", "rice_entitlement_kg", "wheat_entitlement_kg"]],
                           on="beneficiary_id", how="left", suffixes=("", "_ent"))
            over = (_num(m, "rice_quantity_kg") > _num(m, "rice_entitlement_kg")) | \
                   (_num(m, "wheat_quantity_kg") > _num(m, "wheat_entitlement_kg"))
            rule("intent_signals", "intent_within_entitlement", over, "intent must never exceed statutory entitlement")

    if "epos_transactions" in f and "beneficiaries" in f:
        e = f["epos_transactions"]
        e = e[e["status"] == "SUCCESS"]
        used = e.assign(q=_num(e, "quantity_kg")).groupby(["beneficiary_id", "cycle"])["q"].sum().reset_index()
        m = used.merge(f["beneficiaries"][["beneficiary_id", "entitlement_kg"]], on="beneficiary_id", how="left")
        rule("epos_transactions", "distributed_within_entitlement", m["q"] > _num(m, "entitlement_kg"),
             "successful collections exceed entitlement for a beneficiary-cycle")

    if "inventory" in f:
        v = f["inventory"]
        expect = _num(v, "opening_stock_kg") + _num(v, "received_kg") - _num(v, "dispatched_kg") - _num(v, "distributed_kg")
        rule("inventory", "closing_equals_opening_plus_received_minus_out", _num(v, "closing_stock_kg") != expect)

    if "allocations" in f:
        a = f["allocations"]
        rule("allocations", "allocated_not_above_requested", _num(a, "allocated_kg") > _num(a, "requested_kg") + 0.001)

    if "dispatch_manifests" in f:
        m = f["dispatch_manifests"]
        if "dispatch_manifest_items" in f:
            it = f["dispatch_manifest_items"]
            sums = it.assign(p=_num(it, "planned_kg")).groupby("manifest_id")["p"].sum()
            tot = m.set_index("manifest_id")["total_kg"].astype(float)
            diff = (tot - sums.reindex(tot.index).fillna(0)).abs() > 0.01
            report.add("dispatch_manifests", "business", "total_equals_sum_of_items", int(diff.sum()),
                       f"e.g. {list(tot.index[diff][:3])}" if diff.any() else "")
        locked = m["manifest_status"].isin(_LOCKED_STATES)
        rule("dispatch_manifests", "locked_only_if_constraints_ready", locked & (m["constraint_status"] != "READY"),
             "a manifest can be LOCKED or later only when every constraint is READY")
        rule("dispatch_manifests", "locked_has_hash", locked & (m["sha256_hash"].str.strip() == ""))

    manifest_path = data_dir / "07_generated" / "dataset_manifest.json"
    if manifest_path.exists():
        expected = json.loads(manifest_path.read_text(encoding="utf-8")).get("row_counts", {})
        for table, rel, _ in DATASETS:
            name = Path(rel).name
            if table in f and name in expected:
                report.add(table, "business", "row_count_matches_manifest",
                           0 if len(f[table]) == expected[name] else 1,
                           f"manifest says {expected[name]}, file has {len(f[table])}")


def validate(conn: psycopg.Connection, data_dir: Path) -> tuple[Report, dict[str, pd.DataFrame]]:
    report = Report()
    frames = load_frames(data_dir, report)
    cols, fks = _catalog(conn)
    check_schema_and_types(report, frames, cols)
    check_keys(report, frames)
    check_references(report, frames, fks, conn)
    check_business(report, frames, data_dir)
    return report, frames


# --------------------------------------------------------------------------- commit

def _copy(conn: psycopg.Connection, table: str, df: pd.DataFrame) -> None:
    cols = ", ".join(f'"{c}"' for c in df.columns)
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False)  # unquoted empty field == NULL for COPY ... CSV
    with conn.cursor().copy(f"COPY {table} ({cols}) FROM STDIN WITH (FORMAT csv)") as cp:
        cp.write(buf.getvalue())


def _existing_rows(conn: psycopg.Connection) -> dict[str, int]:
    return {t: n for t in TABLES if (n := conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0])}


def import_dataset(url: str | None = None, data_dir: Path = DATA_DIR, imported_by: str = "cli",
                   activate: bool = False, replace: bool = False, dry_run: bool = False) -> dict:
    """Validate and (unless dry_run) load the dataset. Returns a summary dict; never partial-loads."""
    with connect(url) as conn:
        report, frames = validate(conn, data_dir)
        checksum = dataset_checksum(data_dir)
        row_counts = {t: len(df) for t, df in frames.items()}
        summary = {"passed": report.ok, "checksum": checksum, "row_counts": row_counts,
                   "total_rows": sum(row_counts.values()), "report": report.to_json(), "import_id": None,
                   "status": "DRY_RUN_OK" if report.ok else "DRY_RUN_FAILED"}
        if dry_run:
            return summary

        manifest = data_dir / "07_generated" / "dataset_manifest.json"
        meta = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
        name, version = meta.get("dataset_name", data_dir.name), meta.get("version", "unversioned")
        import_id = f"IMP-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{checksum[:8]}"

        def record(status: str) -> None:
            conn.execute(
                """INSERT INTO dataset_imports
                   (import_id, dataset_name, version, status, total_rows, row_counts, checksum, validation_report, imported_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (import_id, name, version, status, summary["total_rows"], json.dumps(row_counts), checksum,
                 json.dumps(report.to_json()), imported_by))

        summary["import_id"] = import_id
        if not report.ok:
            record("REJECTED")
            conn.commit()
            summary["status"] = "REJECTED"
            return summary

        try:
            with conn.transaction():
                if replace:
                    conn.execute("TRUNCATE " + ", ".join(reversed(TABLES)) + " RESTART IDENTITY CASCADE")
                existing = _existing_rows(conn)
                if existing:
                    raise ImportBlocked(f"target already holds data ({existing}); pass replace=True to overwrite")
                for table in TABLES:
                    _copy(conn, table, frames[table])
                record("ACTIVE" if activate else "IMPORTED")
        except ImportBlocked:
            raise
        except psycopg.Error as e:  # the DB constraints are the backstop for anything the checks missed
            record("REJECTED")
            conn.commit()
            summary.update(status="REJECTED", passed=False, error=str(e).splitlines()[0])
            return summary
        summary["status"] = "ACTIVE" if activate else "IMPORTED"
        return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate and import the DemandSYNC dataset")
    ap.add_argument("--path", type=Path, default=DATA_DIR, help="dataset directory (default: DATA_DIR)")
    ap.add_argument("--dry-run", action="store_true", help="validate only, write nothing")
    ap.add_argument("--activate", action="store_true", help="mark the import ACTIVE")
    ap.add_argument("--replace", action="store_true", help="wipe dataset tables first (dev only)")
    ap.add_argument("--by", default="cli", help="who is importing (recorded in dataset_imports)")
    a = ap.parse_args(argv)
    try:
        s = import_dataset(data_dir=a.path, imported_by=a.by, activate=a.activate, replace=a.replace, dry_run=a.dry_run)
    except ImportBlocked as e:
        print(f"BLOCKED: {e}")
        return 2
    rep = s["report"]
    print(f"{s['status']}: {rep['total'] - rep['failed']}/{rep['total']} checks passed, {s['total_rows']} rows, import {s['import_id']}")
    for c in rep["checks"]:
        if c["status"] == "FAIL":
            print(f"  FAIL [{c['level']}] {c['dataset']}.{c['name']}: {c['failed_rows']} rows {c['details']}")
    if s.get("error"):
        print("  DB error:", s["error"])
    return 0 if s["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
