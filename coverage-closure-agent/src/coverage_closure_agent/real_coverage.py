"""Optional real-coverage ingestion path.

This module is an *optional* ingester that reads **real** Verilator coverage
``.dat`` files and lcov ``.info`` files and normalizes them into this repo's
own Pydantic v2 contracts (``CoverageDB`` / ``TriageInputs``) -- the same
``mock-cov`` normalized shape the deterministic :mod:`.triage` engine already
consumes. It is entirely optional: the default pipeline continues to ingest the
hand-authored ``mock-cov-1.0`` JSON bundle and all existing tests are unaffected.

Provenance / attribution
------------------------
The parsing and heuristic-unreachability logic here is a *clean re-implementation*
adapted from the veri-forge reference sources (read-only, not a dependency):

* ``veri_forge/sim/coverage.py``   -- ``parse_coverage_dat``,
  ``extract_toggle_coverage``, ``parse_lcov``, ``classify_unreachable``.
* ``veri_forge/coverage/parser.py`` -- normalization glue.

Only the algorithms were reused; the data model, the normalized output shape,
and the CLI wiring are this repo's own. No code is imported from veri-forge and
there is no runtime dependency on it.

Discipline (unchanged from the rest of the pack)
-----------------------------------------------
The unreachability classification produced here is **HEURISTIC** -- a pattern
match over signal names, never a formal proof and never a closure claim. Every
resulting coverage item is normalized as a plain uncovered point; the downstream
:class:`~.triage.TriageEngine` re-classifies it with cited evidence and always
routes it through the human-review / independent-measurement path.
"""

from __future__ import annotations

import re
from pathlib import Path

from .models import (
    CoverageDB,
    CoverageItem,
    CoverageKind,
    LogBundle,
    RequirementMatrix,
    RTLIntentManifest,
    RTLModule,
    TestManifest,
    TriageInputs,
)

# The format version emitted by this ingester. It is still the normalized
# ``mock-cov`` family shape (so triage is format-agnostic), but the suffix marks
# the provenance as real Verilator/lcov ingestion rather than hand-authored.
REAL_COV_FORMAT_VERSION = "mock-cov-1.0+real-verilator"

# Heuristic unreachability categories. Kept as a public vocabulary so tests and
# callers can reason about them. These mirror the reference classifier's set.
UNREACHABILITY_CATEGORIES = (
    "hardwired_constant",
    "dead_code",
    "counter_ceiling",
    "arch_limit",
    "spec_gap",
    "unknown",
)


# ---------------------------------------------------------------------------
# Verilator coverage.dat parser
# (adapted from veri_forge/sim/coverage.py: parse_coverage_dat)
# ---------------------------------------------------------------------------

# A Verilator coverage line encodes a point as ``C '<key>' <count>`` where the
# key holds attribute pairs. We extract the last single-quoted token as the
# point name and the trailing integer as the hit count. Both the modern
# multi-attribute form and the simple ``C 'name' N`` form are handled.
_DAT_NAME_RE = re.compile(rb"'([^']*)'")
_DAT_COUNT_RE = re.compile(rb"'\s+(\d+)\s*$")


def parse_coverage_dat(path: str | Path) -> dict[str, int]:
    """Parse a Verilator ``coverage.dat`` file into a ``point-name -> count`` map.

    Robust to both the binary-ish attribute form Verilator emits
    (``C '...c_2....'v...' <count>``) and a plain text ``C 'name' <count>``.
    Missing/unreadable files yield an empty mapping (never raises).
    """
    p = Path(path)
    if not p.exists():
        return {}

    counts: dict[str, int] = {}
    try:
        with open(p, "rb") as fh:
            for raw in fh:
                line = raw.rstrip()
                if not line or line[:1] != b"C":
                    continue
                m_count = _DAT_COUNT_RE.search(line)
                if not m_count:
                    continue
                count = int(m_count.group(1))
                # The point name is the last quoted token before the count.
                names = _DAT_NAME_RE.findall(line[: m_count.start() + 1])
                if not names:
                    continue
                name = names[-1].decode("utf-8", errors="replace")
                # Verilator can emit the same point twice; keep the max count.
                counts[name] = max(counts.get(name, 0), count)
    except OSError:
        return {}
    return counts


# ---------------------------------------------------------------------------
# Toggle extraction
# (adapted from veri_forge/sim/coverage.py: extract_toggle_coverage)
# ---------------------------------------------------------------------------


def extract_toggle_coverage(
    dat_counts: dict[str, int],
) -> tuple[int, int, list[tuple[str, str]]]:
    """Return ``(covered, total, uncovered)`` toggle transitions.

    Verilator toggle points end with ``__0`` (0->1) or ``__1`` (1->0). Each is a
    directed transition. ``uncovered`` is a list of ``(signal, direction)``.
    """
    toggle_signals: dict[str, dict[str, int]] = {}
    for key, count in dat_counts.items():
        if key.endswith("__0") or key.endswith("__1"):
            sig = key[:-3]
            direction = "0->1" if key.endswith("__0") else "1->0"
            toggle_signals.setdefault(sig, {})[direction] = count

    total = covered = 0
    uncovered: list[tuple[str, str]] = []
    for sig in sorted(toggle_signals):
        for direction in ("0->1", "1->0"):
            if direction not in toggle_signals[sig]:
                continue
            total += 1
            if toggle_signals[sig][direction] > 0:
                covered += 1
            else:
                uncovered.append((sig, direction))
    return covered, total, uncovered


def _is_toggle_key(key: str) -> bool:
    return key.endswith("__0") or key.endswith("__1")


# ---------------------------------------------------------------------------
# lcov .info parser
# (adapted from veri_forge/sim/coverage.py: parse_lcov)
# ---------------------------------------------------------------------------


def parse_lcov(lcov_path: str | Path) -> list[CoverageItem]:
    """Parse an lcov ``.info`` file into per-line / per-branch coverage items.

    lcov records used:
      * ``SF:<path>``           -- source file for the following records
      * ``DA:<line>,<hits>``    -- line-execution count
      * ``BRDA:<line>,<block>,<branch>,<taken>`` -- branch taken (``-`` == 0)

    Each ``DA``/``BRDA`` becomes a normalized :class:`CoverageItem`. Uncovered
    lines/branches become holes (``hits=0``) the triage engine will pick up.
    Missing/unreadable files yield an empty list (never raises).
    """
    p = Path(lcov_path)
    if not p.exists():
        return []

    items: list[CoverageItem] = []
    cur_file = ""
    cur_module = ""
    try:
        text = p.read_text()
    except OSError:
        return []

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("SF:"):
            cur_file = line[3:].strip()
            cur_module = Path(cur_file).stem or "unknown"
        elif line.startswith("DA:"):
            body = line[3:]
            parts = body.split(",")
            if len(parts) < 2:
                continue
            try:
                src_line = int(parts[0])
                hits = int(parts[1])
            except ValueError:
                continue
            items.append(
                CoverageItem(
                    coverage_id=f"cov.{cur_module}.line.{src_line}",
                    kind=CoverageKind.STATEMENT,
                    hits=max(hits, 0),
                    goal=1,
                    module=cur_module,
                    source_file=cur_file or None,
                    source_line=src_line,
                    description=f"line {src_line} executed",
                )
            )
        elif line.startswith("BRDA:"):
            body = line[5:]
            parts = body.split(",")
            if len(parts) < 4:
                continue
            try:
                src_line = int(parts[0])
            except ValueError:
                continue
            block, branch, taken = parts[1], parts[2], parts[3]
            hits = 0 if taken in ("-", "") else _safe_int(taken)
            items.append(
                CoverageItem(
                    coverage_id=f"cov.{cur_module}.branch.{src_line}.{block}.{branch}",
                    kind=CoverageKind.BRANCH,
                    hits=hits,
                    goal=1,
                    module=cur_module,
                    source_file=cur_file or None,
                    source_line=src_line,
                    description=f"branch {branch} at line {src_line}",
                )
            )
    return items


def _safe_int(s: str) -> int:
    try:
        return max(int(s), 0)
    except ValueError:
        return 0


# ---------------------------------------------------------------------------
# Heuristic unreachability classifier
# (adapted from veri_forge/sim/coverage.py: classify_unreachable)
# ---------------------------------------------------------------------------

_HARDWIRED_PATTERNS = [
    re.compile(r"pready", re.IGNORECASE),
    re.compile(r"bit_en", re.IGNORECASE),
    re.compile(r"vdd|gnd|vcc|power", re.IGNORECASE),
]

_DEAD_CODE_PATTERNS = [
    re.compile(r"tx_frame\[(?:[4-9]\d|[1-9]\d{2,})\]"),
    re.compile(r"paddr\[(?:[6-9]|1\d)\]", re.IGNORECASE),
    re.compile(r"reserved", re.IGNORECASE),
    re.compile(r"_dead|dead_", re.IGNORECASE),
]

_COUNTER_CEILING_PATTERNS = [
    re.compile(r"to_cnt|timeout_cnt|timer_cnt", re.IGNORECASE),
    re.compile(r"max_cnt|cnt_max", re.IGNORECASE),
]

_ARCH_LIMIT_PATTERNS = [
    re.compile(r"clksel|bit_div|clk_div", re.IGNORECASE),
    re.compile(r"ev_to_a|timeout_event", re.IGNORECASE),
]

_SPEC_GAP_PATTERNS = [
    re.compile(r"spec_gap|unspecified|undocumented", re.IGNORECASE),
]


def classify_unreachable(signal: str, direction: str = "", context_hint: str = "") -> str:
    """Heuristically classify *why* a transition/point is uncovered.

    Returns one of :data:`UNREACHABILITY_CATEGORIES`. This is a **heuristic**
    name-pattern match, NOT a formal unreachability proof and NOT a closure
    claim. The result is advisory only.
    """
    subject = f"{signal} {direction} {context_hint}".strip()

    for pat in _HARDWIRED_PATTERNS:
        if pat.search(subject):
            return "hardwired_constant"
    for pat in _DEAD_CODE_PATTERNS:
        if pat.search(subject):
            return "dead_code"
    for pat in _COUNTER_CEILING_PATTERNS:
        if pat.search(subject):
            return "counter_ceiling"
    for pat in _ARCH_LIMIT_PATTERNS:
        if pat.search(subject):
            return "arch_limit"
    for pat in _SPEC_GAP_PATTERNS:
        if pat.search(subject):
            return "spec_gap"
    return "unknown"


# Categories the heuristic treats as "structurally unreachable" -- for these we
# set an exclusion_pragma on the normalized item so the downstream triage engine
# routes them via LIKELY_UNREACHABLE -> inspect/waiver-review (never auto-waived).
_UNREACHABLE_STRUCTURAL = {"hardwired_constant", "dead_code"}


# ---------------------------------------------------------------------------
# Normalization: real artifacts -> CoverageDB / TriageInputs
# ---------------------------------------------------------------------------


def _module_for_signal(signal: str) -> str:
    """Best-effort module name from a hierarchical Verilator signal path."""
    # e.g. "top.dut.fifo.wr_ptr" -> "fifo"; fall back to the head token.
    parts = signal.split(".")
    if len(parts) >= 2:
        return parts[-2]
    return parts[0] if parts and parts[0] else "unknown"


def ingest_real_coverage(
    dat_path: str | Path | None = None,
    lcov_path: str | Path | None = None,
) -> CoverageDB:
    """Ingest real Verilator ``.dat`` and/or lcov ``.info`` into a ``CoverageDB``.

    The result is the same normalized ``mock-cov`` family contract the triage
    engine already consumes, so the existing pipeline is unchanged downstream.

    Uncovered toggle transitions are additionally passed through the HEURISTIC
    :func:`classify_unreachable`; those judged structurally unreachable
    (hardwired/dead-code) are marked with ``exclusion_pragma=True`` so triage
    routes them for human inspection -- never auto-waived, never a closure claim.
    """
    items: list[CoverageItem] = []

    # --- Verilator .dat: toggle + generic line/point coverage ---------------
    if dat_path is not None:
        dat_counts = parse_coverage_dat(dat_path)
        _, _, _ = extract_toggle_coverage(dat_counts)  # validate parse shape

        for key in sorted(dat_counts):
            count = dat_counts[key]
            if _is_toggle_key(key):
                sig = key[:-3]
                direction = "0->1" if key.endswith("__0") else "1->0"
                module = _module_for_signal(sig)
                exclusion = False
                if count == 0:
                    category = classify_unreachable(sig, direction)
                    exclusion = category in _UNREACHABLE_STRUCTURAL
                items.append(
                    CoverageItem(
                        coverage_id=f"cov.{module}.toggle.{_slug(sig)}.{_dir_slug(direction)}",
                        kind=CoverageKind.TOGGLE,
                        hits=max(count, 0),
                        goal=1,
                        module=module,
                        source_file=None,
                        source_line=None,
                        description=f"{sig} toggle {direction}",
                        exclusion_pragma=exclusion,
                    )
                )
            else:
                module = _module_for_signal(key)
                items.append(
                    CoverageItem(
                        coverage_id=f"cov.{module}.point.{_slug(key)}",
                        kind=CoverageKind.STATEMENT,
                        hits=max(count, 0),
                        goal=1,
                        module=module,
                        source_file=None,
                        source_line=None,
                        description=f"{key} coverage point",
                    )
                )

    # --- lcov .info: line + branch coverage ---------------------------------
    if lcov_path is not None:
        items.extend(parse_lcov(lcov_path))

    # Deduplicate by coverage_id (keep the higher hit count) and sort for
    # deterministic output.
    by_id: dict[str, CoverageItem] = {}
    for it in items:
        prev = by_id.get(it.coverage_id)
        if prev is None or it.hits > prev.hits:
            by_id[it.coverage_id] = it
    ordered = [by_id[k] for k in sorted(by_id)]

    return CoverageDB(
        format_version=REAL_COV_FORMAT_VERSION,
        tool="verilator+lcov",
        items=ordered,
    )


def ingest_real_inputs(
    dat_path: str | Path | None = None,
    lcov_path: str | Path | None = None,
) -> TriageInputs:
    """Build a complete :class:`TriageInputs` bundle from real coverage artifacts.

    Real ``.dat``/``.info`` files carry no test manifest, requirement matrix, or
    RTL intent -- only measured coverage. We therefore emit the coverage DB plus
    *empty but valid* companion manifests, deriving the RTL module list from the
    observed coverage so the bundle validates and flows straight into
    :func:`coverage_closure_agent.triage.TriageEngine.run`.

    With no linked tests/requirements, most holes will land in the honest
    ``no_linked_test`` / ``no_requirement_mapping`` categories -- an accurate
    reflection of ingesting bare coverage with no surrounding testplan.
    """
    cov = ingest_real_coverage(dat_path=dat_path, lcov_path=lcov_path)

    modules: dict[str, str | None] = {}
    for it in cov.items:
        # First non-null source_file wins as the module's representative file.
        if it.module not in modules or (modules[it.module] is None and it.source_file):
            modules[it.module] = it.source_file

    rtl = RTLIntentManifest(
        top=None,
        modules=[
            RTLModule(name=name, source_file=src, dead_code_hints=[])
            for name, src in sorted(modules.items())
        ],
    )

    return TriageInputs(
        coverage=cov,
        tests=TestManifest(tests=[]),
        rtl=rtl,
        requirements=RequirementMatrix(links=[]),
        logs=LogBundle(entries=[]),
    )


def _slug(name: str) -> str:
    """Make a coverage_id-safe token from a hierarchical signal name."""
    return re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_") or "x"


def _dir_slug(direction: str) -> str:
    return "0to1" if direction == "0->1" else "1to0"
