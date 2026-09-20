"""Orchestration: generate mutants, classify them, score, and build a report.

This module contains the deterministic scoring rule required by the spec:
the mutation score EXCLUDES invalid and inconclusive mutants.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict

from .executor import get_executor
from .models import (
    Mutant,
    MutantStatus,
    MutationOperator,
    MutationReport,
    PropertyRef,
    ScoreBreakdown,
    SurvivingMutant,
)
from .operators import generate_mutants
from .sva import parse_properties

TOOL_VERSION = "0.1.0"


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def compute_score(results: list) -> ScoreBreakdown:
    """Compute the mutation score, excluding invalid and inconclusive mutants."""
    counts = {s: 0 for s in MutantStatus}
    for r in results:
        counts[r.status] += 1

    scored = counts[MutantStatus.DETECTED] + counts[MutantStatus.SURVIVED]
    # TIMEOUT / ERROR are execution failures. They are NOT passes and are NOT
    # counted toward detection; they are also excluded from the denominator
    # (they represent no valid detection evidence), matching the rule that a
    # timeout/error is never a PASS.
    score = counts[MutantStatus.DETECTED] / scored if scored else 0.0
    return ScoreBreakdown(
        total=len(results),
        detected=counts[MutantStatus.DETECTED],
        survived=counts[MutantStatus.SURVIVED],
        invalid=counts[MutantStatus.INVALID],
        timeout=counts[MutantStatus.TIMEOUT],
        error=counts[MutantStatus.ERROR],
        inconclusive=counts[MutantStatus.INCONCLUSIVE],
        scored=scored,
        mutation_score=round(score, 6),
    )


def run_mutation_analysis(
    module: str,
    rtl_source: str,
    rtl_file: str,
    property_texts: dict[str, str],
    operators: list[MutationOperator] | None = None,
    executor_name: str = "mock",
) -> MutationReport:
    """Run the full pipeline and return a :class:`MutationReport`.

    Parameters
    ----------
    module:
        Logical module name used in mutant IDs and locations.
    rtl_source:
        RTL text to mutate.
    rtl_file:
        Path recorded in provenance / report.
    property_texts:
        Mapping of property-file-path -> SVA file contents.
    operators:
        Subset of operators to apply; None means all.
    executor_name:
        Name of the executor adapter (currently only ``mock``).
    """
    executor = get_executor(executor_name)

    properties: list[PropertyRef] = []
    for text in property_texts.values():
        properties.extend(parse_properties(text))

    mutants: list[Mutant] = generate_mutants(module, rtl_source, operators)
    results = [
        executor.classify(m, rtl_source, properties) for m in mutants
    ]
    score = compute_score(results)

    mutant_by_id = {m.mutant_id: m for m in mutants}

    # Surviving mutants overall.
    survivors = [r for r in results if r.status == MutantStatus.SURVIVED]

    surviving_by_operator: dict[str, list[str]] = defaultdict(list)
    for r in survivors:
        surviving_by_operator[r.operator.value].append(r.mutant_id)

    # Surviving *by property*: for each property, which survivors did it fail to
    # detect (i.e. every survivor is undetected by every property; we list them
    # per property to make the report actionable per assertion).
    surviving_by_property: dict[str, list[str]] = {p.name: [] for p in properties}
    for r in survivors:
        for p in properties:
            surviving_by_property[p.name].append(r.mutant_id)

    surviving_mutants = [
        SurvivingMutant(
            mutant_id=r.mutant_id,
            operator=r.operator,
            description=mutant_by_id[r.mutant_id].description,
            diff_summary=mutant_by_id[r.mutant_id].diff.unified,
        )
        for r in survivors
    ]

    provenance = {
        "tool": "assertion-mutation-agent",
        "tool_version": TOOL_VERSION,
        "git_sha": "PLACEHOLDER",
        "executor": executor_name,
        "rtl_sha256_16": _hash(rtl_source),
        "property_sha256_16": _hash("".join(property_texts.values())),
        "operators": ",".join(
            o.value for o in (operators or list(MutationOperator))
        ),
        "seed": "deterministic",
    }

    return MutationReport(
        module=module,
        rtl_file=rtl_file,
        property_files=list(property_texts.keys()),
        executor=executor_name,
        provenance=provenance,
        score=score,
        results=results,
        surviving_by_property={
            k: v for k, v in surviving_by_property.items() if v
        },
        surviving_by_operator=dict(surviving_by_operator),
        surviving_mutants=surviving_mutants,
    )


def render_markdown(report: MutationReport) -> str:
    """Render a human-readable Markdown summary of a mutation report."""
    s = report.score
    lines: list[str] = []
    lines.append(f"# Mutation Report - `{report.module}`")
    lines.append("")
    lines.append(f"- RTL file: `{report.rtl_file}`")
    lines.append(f"- Property files: {', '.join(f'`{p}`' for p in report.property_files)}")
    exec_note = (
        "mock; no real simulator"
        if report.executor == "mock"
        else "real simulator (Verilator)"
        if report.executor == "verilator"
        else report.executor
    )
    lines.append(f"- Executor: `{report.executor}` ({exec_note})")
    lines.append(f"- Tool version: `{report.provenance.get('tool_version')}`")
    lines.append(f"- RTL hash: `{report.provenance.get('rtl_sha256_16')}`")
    lines.append("")
    lines.append("## Score (excludes invalid + inconclusive)")
    lines.append("")
    lines.append(f"- **Mutation score: {s.mutation_score:.2%}** ({s.detected}/{s.scored} scored)")
    lines.append(f"- Total mutants: {s.total}")
    lines.append(
        f"- detected={s.detected} survived={s.survived} invalid={s.invalid} "
        f"timeout={s.timeout} error={s.error} inconclusive={s.inconclusive}"
    )
    lines.append("")
    lines.append("## Surviving mutants by operator")
    lines.append("")
    if report.surviving_by_operator:
        for op, ids in sorted(report.surviving_by_operator.items()):
            lines.append(f"- `{op}`: {len(ids)} survivor(s)")
    else:
        lines.append("- None")
    lines.append("")
    lines.append("## Surviving mutants (undetected mutations requiring investigation)")
    lines.append("")
    if report.surviving_mutants:
        for sm in report.surviving_mutants:
            lines.append(f"### `{sm.mutant_id}` ({sm.operator.value})")
            lines.append(f"{sm.description}")
            lines.append("")
            lines.append("```diff")
            lines.append(sm.diff_summary)
            lines.append("```")
            lines.append("")
    else:
        lines.append("- None. (Not a proof the suite is complete.)")
    lines.append("")
    lines.append("> A surviving mutant is an *undetected mutation requiring "
                 "investigation*, NOT proof that an assertion is wrong. Mutation "
                 "scoring is a heuristic property-quality signal, not formal signoff.")
    lines.append("")
    return "\n".join(lines)
