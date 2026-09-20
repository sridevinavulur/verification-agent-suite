"""SQLite ledger + data-access layer.

Stores benchmark suites, experiment plans, and run records with full provenance.
The ledger is the durable source of truth for ``summarize`` and ``compare``. All
writes go through typed Pydantic models so nothing malformed lands in the DB.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .models import (
    BenchmarkSuite,
    ExperimentPlan,
    MachineMetadata,
    RunRecord,
    RunStatus,
    ValidationStatus,
)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS suites (
    suite_id       TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL,
    description    TEXT NOT NULL,
    payload_json   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plans (
    plan_id         TEXT PRIMARY KEY,
    suite_id        TEXT NOT NULL,
    catalog_version TEXT NOT NULL,
    policy_name     TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    payload_json    TEXT NOT NULL,
    FOREIGN KEY (suite_id) REFERENCES suites(suite_id)
);

CREATE TABLE IF NOT EXISTS runs (
    run_id            TEXT PRIMARY KEY,
    plan_id           TEXT NOT NULL,
    benchmark_id      TEXT NOT NULL,
    design_sha        TEXT NOT NULL,
    property_sha      TEXT NOT NULL,
    input_hash        TEXT NOT NULL,
    tool_name         TEXT NOT NULL,
    tool_version      TEXT NOT NULL,
    config_id         TEXT NOT NULL,
    catalog_version   TEXT NOT NULL,
    command_line      TEXT NOT NULL,
    seed              INTEGER NOT NULL,
    machine_json      TEXT NOT NULL,
    start_time        TEXT NOT NULL,
    end_time          TEXT NOT NULL,
    cpu_time_s        REAL NOT NULL,
    wall_time_s       REAL NOT NULL,
    peak_memory_mb    REAL NOT NULL,
    return_code       INTEGER NOT NULL,
    status            TEXT NOT NULL,
    validation_status TEXT NOT NULL,
    rationale         TEXT NOT NULL,
    artifact_path     TEXT,
    artifact_hash     TEXT,
    payload_json      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runs_plan ON runs(plan_id);
CREATE INDEX IF NOT EXISTS idx_runs_bench ON runs(benchmark_id);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
"""


class Ledger:
    """Thin, typed data-access layer over a SQLite file (or ``:memory:``)."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> Ledger:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ----------------------------- suites ----------------------------- #
    def save_suite(self, suite: BenchmarkSuite) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO suites (suite_id, schema_version, description, payload_json) "
            "VALUES (?, ?, ?, ?)",
            (suite.suite_id, suite.schema_version, suite.description,
             suite.model_dump_json()),
        )
        self.conn.commit()

    def get_suite(self, suite_id: str) -> BenchmarkSuite | None:
        row = self.conn.execute(
            "SELECT payload_json FROM suites WHERE suite_id = ?", (suite_id,)
        ).fetchone()
        if row is None:
            return None
        return BenchmarkSuite.model_validate_json(row["payload_json"])

    # ----------------------------- plans ------------------------------ #
    def save_plan(self, plan: ExperimentPlan) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO plans "
            "(plan_id, suite_id, catalog_version, policy_name, created_at, payload_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (plan.plan_id, plan.suite_id, plan.catalog_version, plan.policy_name,
             plan.created_at.isoformat(), plan.model_dump_json()),
        )
        self.conn.commit()

    def get_plan(self, plan_id: str) -> ExperimentPlan | None:
        row = self.conn.execute(
            "SELECT payload_json FROM plans WHERE plan_id = ?", (plan_id,)
        ).fetchone()
        if row is None:
            return None
        return ExperimentPlan.model_validate_json(row["payload_json"])

    # ------------------------------ runs ------------------------------ #
    def save_run(self, run: RunRecord) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO runs (
                run_id, plan_id, benchmark_id, design_sha, property_sha, input_hash,
                tool_name, tool_version, config_id, catalog_version, command_line, seed,
                machine_json, start_time, end_time, cpu_time_s, wall_time_s, peak_memory_mb,
                return_code, status, validation_status, rationale, artifact_path,
                artifact_hash, payload_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                run.run_id, run.plan_id, run.benchmark_id, run.design_sha, run.property_sha,
                run.input_hash, run.tool_name, run.tool_version, run.config_id,
                run.catalog_version, run.command_line, run.seed,
                run.machine.model_dump_json(), run.start_time.isoformat(),
                run.end_time.isoformat(), run.cpu_time_s, run.wall_time_s,
                run.peak_memory_mb, run.return_code, run.status.value,
                run.validation_status.value, run.rationale, run.artifact_path,
                run.artifact_hash, run.model_dump_json(),
            ),
        )
        self.conn.commit()

    def get_run(self, run_id: str) -> RunRecord | None:
        row = self.conn.execute(
            "SELECT payload_json FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return None
        return RunRecord.model_validate_json(row["payload_json"])

    def runs_for_plan(self, plan_id: str) -> list[RunRecord]:
        rows = self.conn.execute(
            "SELECT payload_json FROM runs WHERE plan_id = ? ORDER BY run_id", (plan_id,)
        ).fetchall()
        return [RunRecord.model_validate_json(r["payload_json"]) for r in rows]

    def all_runs(self) -> list[RunRecord]:
        rows = self.conn.execute(
            "SELECT payload_json FROM runs ORDER BY run_id"
        ).fetchall()
        return [RunRecord.model_validate_json(r["payload_json"]) for r in rows]

    # --------------------------- ingestion ---------------------------- #
    def ingest_result_json(self, path: str | Path) -> RunRecord:
        """Ingest an externally-produced run record JSON into the ledger.

        Validates against the RunRecord schema (rejecting malformed provenance)
        before persisting. This is the sanctioned path for results produced by a
        real backend adapter outside this process.
        """
        data = json.loads(Path(path).read_text())
        record = RunRecord.model_validate(data)
        self.save_run(record)
        return record


def machine_metadata() -> MachineMetadata:
    """Capture reproducibility-relevant host metadata (no PII beyond hostname)."""
    import os
    import platform
    import socket

    return MachineMetadata(
        hostname=socket.gethostname(),
        platform=platform.platform(),
        python_version=platform.python_version(),
        cpu_count=os.cpu_count() or 1,
    )


# Re-exported so callers can build guards without importing enums twice.
__all__ = [
    "Ledger",
    "machine_metadata",
    "RunStatus",
    "ValidationStatus",
    "datetime",
]
