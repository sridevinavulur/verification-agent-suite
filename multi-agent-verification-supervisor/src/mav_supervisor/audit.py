"""Append-only JSONL audit log and artifact-store layout.

Artifact store layout (under ``root``):

    <root>/
      <task_id>/
        audit.jsonl          # one AuditEvent per line, append-only
        evidence_packet.json # final evidence packet
        run_record.json      # provenance for the executed run (if any)

Every state transition and gate decision is written as an ``AuditEvent``. The log
is append-only: the supervisor only ever appends, and each event carries a
monotonically increasing ``seq``.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import AuditEvent, WorkflowState


class AuditLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seq = 0
        # Resume seq if the file already exists (append-only semantics).
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        self._seq += 1

    def append(
        self,
        task_id: str,
        from_state: WorkflowState,
        to_state: WorkflowState,
        event: str,
        detail: str = "",
        actor: str = "supervisor",
    ) -> AuditEvent:
        ev = AuditEvent(
            seq=self._seq,
            task_id=task_id,
            from_state=from_state,
            to_state=to_state,
            event=event,
            detail=detail,
            actor=actor,  # type: ignore[arg-type]
        )
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(ev.model_dump_json())
            fh.write("\n")
        self._seq += 1
        return ev

    def read_all(self) -> list[AuditEvent]:
        events: list[AuditEvent] = []
        if not self.path.exists():
            return events
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    events.append(AuditEvent.model_validate_json(line))
        return events


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def task_dir(self, task_id: str) -> Path:
        d = self.root / task_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def audit_path(self, task_id: str) -> Path:
        return self.task_dir(task_id) / "audit.jsonl"

    def write_json(self, task_id: str, name: str, obj: object) -> Path:
        p = self.task_dir(task_id) / name
        if hasattr(obj, "model_dump_json"):
            p.write_text(obj.model_dump_json(indent=2), encoding="utf-8")  # type: ignore[attr-defined]
        else:
            p.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
        return p
