"""CRAVS integration for the debug-analysis stage.

Wraps an optional external multi-agent debug engine ("CRAVS") exposed as a
`cravs_core.py` module. The engine is NOT bundled with this repo; it is resolved
at runtime. Provides a clean interface:
    run_cravs_analysis(log, rtl, spec) -> structured findings.

The engine is resolved via the CRAVS_PATH env var, or auto-detected relative to
this package when embedded in a host monorepo. Falls back to LLM-only analysis
when the engine is unavailable.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models import Bug


# ── CRAVS loader ─────────────────────────────────────────────────────────────

def _load_cravs() -> Optional[Any]:
    """Dynamically import cravs_core from CRAVS_PATH or auto-detected locations."""
    search_paths = []

    # 1. Explicit env var
    env = os.getenv("CRAVS_PATH")
    if env:
        search_paths.append(Path(env) / "cravs_core.py")

    # 2. Auto-detect relative to this package (when embedded in a host monorepo)
    here = Path(__file__).resolve()
    for up in range(6):
        candidate = here
        for _ in range(up):
            candidate = candidate.parent
        candidate = candidate / "deps" / "cravs" / "cravs_core.py"
        search_paths.append(candidate)

    # 3. Installed package
    try:
        import cravs.cravs_core as cc
        return cc
    except ImportError:
        pass

    for p in search_paths:
        if p.exists():
            spec = importlib.util.spec_from_file_location("cravs_core", p)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules["cravs_core"] = mod
                spec.loader.exec_module(mod)
                return mod

    return None


_CRAVS_MOD = None
_CRAVS_LOADED = False


def _get_cravs():
    global _CRAVS_MOD, _CRAVS_LOADED
    if not _CRAVS_LOADED:
        _CRAVS_MOD = _load_cravs()
        _CRAVS_LOADED = True
    return _CRAVS_MOD


# ── Public API ───────────────────────────────────────────────────────────────

def run_cravs_analysis(
    log_files: List[str],
    sim_log: str,
    rtl_files: List[str],
    spec_text: str,
    test_name: str = "unknown",
    waveform_path: Optional[str] = None,
    *,
    llm_client: Optional[Any] = None,
) -> List[Bug]:
    """
    Run CRAVS on simulation failure evidence.

    Returns a list of Bug objects describing root causes and suggested fixes.
    Falls back to LLM-only analysis when CRAVS is unavailable.
    """
    cravs = _get_cravs()

    if cravs is not None:
        return _run_via_cravs(
            cravs, log_files, sim_log, rtl_files, spec_text, test_name, waveform_path
        )
    else:
        return _run_via_llm(
            log_files, sim_log, rtl_files, spec_text, test_name, llm_client
        )


def _run_via_cravs(
    cravs: Any,
    log_files: List[str],
    sim_log: str,
    rtl_files: List[str],
    spec_text: str,
    test_name: str,
    waveform_path: Optional[str],
) -> List[Bug]:
    """Drive the full CRAVS multi-agent debug pipeline."""
    bugs: List[Bug] = []
    try:
        kb = cravs.CravsKnowledgeBase()

        # Build a DebuggingSession
        session = cravs.DebuggingSession(
            session_id=f"vf_{test_name[:20]}",
            log_files=log_files,
            test_file=test_name,
            fsdb_file=waveform_path or "",
        )

        # Try to instantiate and run the orchestrator if available
        if hasattr(cravs, "CravsOrchestrator"):
            orch = cravs.CravsOrchestrator(kb=kb)
            evidence_list = orch.analyze(session, rtl_files=rtl_files, spec=spec_text)
        else:
            # Direct multi-agent call pattern used in standalone cravs
            evidence_list = _cravs_direct_analyze(cravs, session, kb, spec_text)

        for ev in evidence_list:
            bugs.append(Bug(
                id=f"CRAVS-{test_name[:8]}-{len(bugs)+1}",
                severity="P1" if getattr(ev, "confidence", 0.5) > 0.7 else "P2",
                failure_type="RTL_BUG",
                test=test_name,
                description=getattr(ev, "finding", "Unknown failure"),
                root_cause=getattr(ev, "root_cause_hypothesis", "See CRAVS log"),
                suggested_fix="; ".join(getattr(ev, "recommended_actions", [])),
                status="open",
            ))
    except Exception as exc:
        bugs.append(Bug(
            id=f"CRAVS-ERR-{test_name[:8]}",
            severity="P2",
            failure_type="RTL_BUG",
            test=test_name,
            description=f"CRAVS analysis encountered an error: {exc}",
            root_cause="CRAVS analysis failed — inspect sim log manually.",
            suggested_fix="Check CRAVS_PATH env var and ensure cravs_core.py is accessible.",
            status="open",
        ))
    return bugs


def _cravs_direct_analyze(cravs: Any, session: Any, kb: Any, spec: str) -> List[Any]:
    """Call individual CRAVS agents when the orchestrator class is not present."""
    evidence = []
    agent_types_to_run = [
        getattr(cravs.CravsAgentType, "LOG_ANALYZER", None),
        getattr(cravs.CravsAgentType, "PROTOCOL_EXPERT", None),
        getattr(cravs.CravsAgentType, "TIMING_ANALYZER", None),
    ]
    for agent_type in agent_types_to_run:
        if agent_type is None:
            continue
        try:
            if hasattr(cravs, "run_agent"):
                result = cravs.run_agent(agent_type, session, kb, spec=spec)
                if result:
                    evidence.append(result)
        except Exception:
            pass
    return evidence


def _run_via_llm(
    log_files: List[str],
    sim_log: str,
    rtl_files: List[str],
    spec_text: str,
    test_name: str,
    llm_client: Optional[Any],
) -> List[Bug]:
    """LLM-only root cause analysis when CRAVS is unavailable."""
    from ..llm.client import simple_call

    # Truncate inputs to stay within token budget
    log_snippet = sim_log[-4000:] if sim_log else "(no log)"
    spec_snippet = spec_text[:2000] if spec_text else "(no spec)"

    system = (
        "You are an expert hardware verification debug analyst. "
        "Analyze simulation failures and provide structured root cause analysis."
    )
    user = f"""
Test: {test_name}
Simulation log (tail):
```
{log_snippet}
```
Spec excerpt:
```
{spec_snippet}
```

Provide a JSON array of bugs found. Each bug:
{{
  "description": "What failed",
  "root_cause": "Why it failed in the RTL/TB",
  "suggested_fix": "What to change to fix it"
}}
Output ONLY valid JSON.
"""
    bugs: List[Bug] = []
    try:
        response = simple_call(system, user, client=llm_client)
        # Extract JSON from response
        json_match = None
        for pattern in [r"\[\s*\{.*\}\s*\]", r"\{.*\}"]:
            import re
            m = re.search(pattern, response, re.DOTALL)
            if m:
                json_match = m.group(0)
                break
        if json_match:
            data = json.loads(json_match)
            if isinstance(data, dict):
                data = [data]
            for i, item in enumerate(data):
                bugs.append(Bug(
                    id=f"LLM-{test_name[:8]}-{i+1}",
                    severity="P2",
                    failure_type="RTL_BUG",
                    test=test_name,
                    description=item.get("description", "Unknown"),
                    root_cause=item.get("root_cause", "LLM analysis"),
                    suggested_fix=item.get("suggested_fix", "See log"),
                    status="open",
                ))
    except Exception as exc:
        bugs.append(Bug(
            id=f"LLM-ERR-{test_name[:8]}",
            severity="P2",
            failure_type="RTL_BUG",
            test=test_name,
            description=f"LLM debug analysis failed: {exc}",
            root_cause="Could not complete automatic root cause analysis.",
            suggested_fix="Inspect simulation log manually.",
            status="open",
        ))
    return bugs
