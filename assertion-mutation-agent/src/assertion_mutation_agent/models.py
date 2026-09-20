"""Typed data contracts for the Assertion Mutation Agent.

All contracts are Pydantic v2 models that *validate* their inputs, not merely
annotate them. The vocabulary for classification results follows the shared
BUILD_STANDARD: a TIMEOUT / ERROR / INCONCLUSIVE result is never a PASS, and a
surviving mutant is an "undetected mutation requiring investigation", never
proof that an assertion is wrong.
"""

from __future__ import annotations

import hashlib
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MutationOperator(StrEnum):
    """The source-mutation operators supported on the constrained Verilog subset."""

    RELATIONAL_FLIP = "relational_flip"
    BOOLEAN_NEGATION = "boolean_negation"
    ENABLE_REMOVAL = "enable_removal"
    RESET_POLARITY_FLIP = "reset_polarity_flip"
    RESET_VALUE_CHANGE = "reset_value_change"
    COUNTER_INCDEC_CHANGE = "counter_incdec_change"
    ASSIGN_OPERAND_SWAP = "assign_operand_swap"
    VALID_READY_GATING_REMOVAL = "valid_ready_gating_removal"
    WIDTH_TRUNCATION = "width_truncation"


class MutantStatus(StrEnum):
    """Classification of a mutant after execution by the configured adapter.

    DETECTED     - at least one property caught the injected defect.
    SURVIVED     - no property caught it (undetected mutation to investigate).
    INVALID      - the mutant is not a well-formed / meaningful design change
                   (e.g. it did not change the source). Excluded from scoring.
    TIMEOUT      - the executor exceeded its budget. Never counted as PASS.
    ERROR        - the executor failed to run the mutant.
    INCONCLUSIVE - no detected/survived conclusion could be reached. Excluded
                   from scoring.
    """

    DETECTED = "detected"
    SURVIVED = "survived"
    INVALID = "invalid"
    TIMEOUT = "timeout"
    ERROR = "error"
    INCONCLUSIVE = "inconclusive"


class SourceLocation(BaseModel):
    """A 1-based line/column span into a source file."""

    model_config = ConfigDict(frozen=True)

    file: str
    line: int = Field(ge=1)
    col_start: int = Field(ge=1)
    col_end: int = Field(ge=1)

    @field_validator("col_end")
    @classmethod
    def _end_after_start(cls, v: int, info) -> int:  # type: ignore[no-untyped-def]
        start = info.data.get("col_start")
        if start is not None and v < start:
            raise ValueError("col_end must be >= col_start")
        return v


class SourceDiff(BaseModel):
    """The exact textual change a mutation makes at a location."""

    model_config = ConfigDict(frozen=True)

    location: SourceLocation
    original_text: str
    mutated_text: str
    original_line: str
    mutated_line: str

    @property
    def unified(self) -> str:
        """A tiny single-line unified-style diff for human reports."""
        loc = self.location
        return (
            f"@@ {loc.file}:{loc.line} @@\n"
            f"- {self.original_line}\n"
            f"+ {self.mutated_line}"
        )


class Mutant(BaseModel):
    """A single mutated variant of the design."""

    mutant_id: str
    operator: MutationOperator
    description: str
    diff: SourceDiff
    # Signals / identifiers the mutation touches. Used by the mock executor to
    # decide whether any property could observe the defect.
    mutated_signals: list[str] = Field(default_factory=list)
    mutated_source: str

    @staticmethod
    def make_id(
        module: str,
        operator: MutationOperator,
        line: int,
        col: int,
        original_text: str,
        mutated_text: str,
    ) -> str:
        """Deterministic, stable mutant ID.

        Stability: identical (module, operator, position, text) always yields
        the same ID across runs and machines, so golden reports are reproducible.
        """
        payload = f"{module}|{operator.value}|{line}:{col}|{original_text}=>{mutated_text}"
        digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8]
        return f"{module}.{operator.value}.{line}.{digest}"


class PropertyRef(BaseModel):
    """A parsed SVA property and the design signals it references."""

    name: str
    text: str
    referenced_signals: list[str] = Field(default_factory=list)


class MutantResult(BaseModel):
    """The outcome of classifying one mutant against the property suite."""

    mutant_id: str
    operator: MutationOperator
    status: MutantStatus
    detected_by: list[str] = Field(
        default_factory=list,
        description="Property names that detected the mutant (if DETECTED).",
    )
    detail: str = ""
    executor: str = "mock"


class ScoreBreakdown(BaseModel):
    """Aggregate mutation score with counts by status."""

    total: int
    detected: int
    survived: int
    invalid: int
    timeout: int
    error: int
    inconclusive: int
    scored: int = Field(
        description="Mutants included in the score (excludes invalid + inconclusive)."
    )
    mutation_score: float = Field(
        description="detected / scored, in [0, 1]. None-equivalent 0.0 when scored==0."
    )


class SurvivingMutant(BaseModel):
    """A surviving mutant surfaced in the report for investigation."""

    mutant_id: str
    operator: MutationOperator
    description: str
    diff_summary: str


class MutationReport(BaseModel):
    """The complete, machine-readable mutation report."""

    model_config = ConfigDict()

    schema_version: str = "1.0"
    module: str
    rtl_file: str
    property_files: list[str] = Field(default_factory=list)
    executor: str = "mock"
    provenance: dict[str, str] = Field(default_factory=dict)

    score: ScoreBreakdown
    results: list[MutantResult] = Field(default_factory=list)

    surviving_by_property: dict[str, list[str]] = Field(
        default_factory=dict,
        description="property name -> [mutant_id] it FAILED to detect (survivors).",
    )
    surviving_by_operator: dict[str, list[str]] = Field(
        default_factory=dict,
        description="operator -> [mutant_id] survivors.",
    )
    surviving_mutants: list[SurvivingMutant] = Field(default_factory=list)
