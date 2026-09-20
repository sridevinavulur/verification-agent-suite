"""Pydantic v2 data contracts for the verification-agent-factory.

The central contract is :class:`VerificationAgentManifest` (prompt pack 4.2). The
manifest is the single source of truth used to scaffold a new agent repository,
export JSON Schema, and generate documentation.

All models are strict (``extra="forbid"``) so typos or unknown fields are caught
at validation time rather than silently ignored.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class MaturityLevel(StrEnum):
    """How much evidence backs the agent's behaviour."""

    PROTOTYPE = "prototype"
    EVALUATED_PROTOTYPE = "evaluated_prototype"
    RESEARCH_TOOL = "research_tool"
    PRODUCTION_CANDIDATE = "production_candidate"


class ReleaseMode(StrEnum):
    """Whether the generated repo is intended for public release."""

    PUBLIC = "public"
    PRIVATE = "private"


class AgentCategory(StrEnum):
    """Supported agent categories (prompt pack 4.1)."""

    RTL_ANALYSIS = "rtl_analysis"
    VERIFICATION_PLANNING = "verification_planning"
    SVA_GENERATION = "sva_generation"
    ASSERTION_REVIEW = "assertion_review"
    PROPERTY_MUTATION = "property_mutation"
    FORMAL_RUN_ORCHESTRATION = "formal_run_orchestration"
    COUNTEREXAMPLE_TRIAGE = "counterexample_triage"
    COVERAGE_ANALYSIS = "coverage_analysis"
    PROTOCOL_CHECKING = "protocol_checking"
    REGISTER_CSR_VERIFICATION = "register_csr_verification"
    RESET_ANALYSIS = "reset_analysis"
    CDC_RDC_TRIAGE = "cdc_rdc_triage"
    EQUIVALENCE_TRIAGE = "equivalence_triage"
    REGRESSION_INTELLIGENCE = "regression_intelligence"
    KNOWLEDGE_GRAPH = "knowledge_graph"


class ArtifactKind(StrEnum):
    """Coarse artifact types an agent consumes or produces."""

    RTL = "rtl"
    SVA = "sva"
    NATURAL_LANGUAGE_REQUIREMENT = "natural_language_requirement"
    JSON_MANIFEST = "json_manifest"
    COVERAGE_DB = "coverage_db"
    WAVEFORM = "waveform"
    TOOL_LOG = "tool_log"
    REGISTER_MAP = "register_map"
    REPORT = "report"
    RUN_LEDGER = "run_ledger"


# ---------------------------------------------------------------------------
# Nested contracts
# ---------------------------------------------------------------------------


class ClaimPolicy(BaseModel):
    """The explicit, human-readable claim strings required by prompt pack 4.2.

    These map one-to-one to the mandated sentences. They exist so that every
    generated agent forces its author to state, in plain English, what the agent
    may and may not claim, and how results are interpreted. The factory refuses
    to generate a repo whose author left these blank or trivially short.
    """

    model_config = ConfigDict(extra="forbid")

    may_claim: str = Field(
        ...,
        description='Completes "This agent may claim..."',
        min_length=15,
    )
    must_not_claim: str = Field(
        ...,
        description='Completes "This agent must not claim..."',
        min_length=15,
    )
    passing_result_means: str = Field(
        ...,
        description='Completes "A passing result means..."',
        min_length=15,
    )
    timeout_or_unknown_means: str = Field(
        ...,
        description='Completes "A timeout or unknown result means..."',
        min_length=15,
    )
    human_review_required_when: str = Field(
        ...,
        description='Completes "Human review is required when..."',
        min_length=15,
    )

    @field_validator(
        "may_claim",
        "must_not_claim",
        "passing_result_means",
        "timeout_or_unknown_means",
        "human_review_required_when",
    )
    @classmethod
    def _not_placeholder(cls, v: str) -> str:
        stripped = v.strip()
        lowered = stripped.lower()
        placeholders = {"tbd", "todo", "n/a", "na", "none", "..."}
        if lowered in placeholders:
            raise ValueError("claim strings must be explicit, not a placeholder")
        return stripped


class LlmRole(BaseModel):
    """An optional LLM responsibility with its deterministic guardrail."""

    model_config = ConfigDict(extra="forbid")

    role: str = Field(..., min_length=3, description="What the LLM proposes.")
    deterministic_check: str = Field(
        ...,
        min_length=3,
        description="Deterministic tool that validates the LLM output.",
    )


class ValidationGate(BaseModel):
    """A deterministic gate that must pass before results are trusted."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=2)
    description: str = Field(..., min_length=5)
    blocking: bool = Field(
        default=True,
        description="If true, failure of this gate blocks a PASS classification.",
    )


class EvidenceMetric(BaseModel):
    """A measurable success metric tied to how it is computed."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=2)
    description: str = Field(..., min_length=5)
    how_measured: str = Field(..., min_length=5)


class BenchmarkManifest(BaseModel):
    """Description of the public benchmark demonstrating usefulness."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=2)
    description: str = Field(..., min_length=5)
    public_source: str = Field(
        ...,
        min_length=3,
        description="Where the public benchmark data comes from.",
    )
    license: str = Field(..., min_length=2)


class ReproducibilityRequirements(BaseModel):
    """Provenance fields that every run of the generated agent must record."""

    model_config = ConfigDict(extra="forbid")

    record_git_sha: bool = True
    record_input_hashes: bool = True
    record_tool_versions: bool = True
    record_seed: bool = True
    record_command_line: bool = True
    record_runtime_and_memory: bool = True


class DataClassificationPolicy(BaseModel):
    """What data is permitted and what must never be committed."""

    model_config = ConfigDict(extra="forbid")

    allowed_inputs: str = Field(
        default="Public, non-proprietary RTL / specs / logs only.",
        min_length=5,
    )
    must_not_commit: list[str] = Field(
        default_factory=lambda: [
            "API keys, tokens, passwords, certificates",
            "employer / customer / partner names",
            "proprietary RTL, logs, waveforms, tool scripts",
            "internal hostnames, usernames, filesystem paths",
        ],
        min_length=1,
    )


class SecurityPolicy(BaseModel):
    """Security posture for the generated repository."""

    model_config = ConfigDict(extra="forbid")

    requires_credentials_by_default: bool = Field(
        default=False,
        description="Must be False: CI runs with no secrets.",
    )
    secret_scan_on_release: bool = True
    vulnerability_contact: str = Field(
        default="See SECURITY.md",
        min_length=3,
    )

    @field_validator("requires_credentials_by_default")
    @classmethod
    def _no_default_creds(cls, v: bool) -> bool:
        if v:
            raise ValueError(
                "agents must not require credentials by default (BUILD_STANDARD.md)"
            )
        return v


class ProvenanceMetadata(BaseModel):
    """Authoring provenance for the manifest itself."""

    model_config = ConfigDict(extra="forbid")

    author_role: str = Field(..., min_length=2)
    created_utc: str = Field(
        ...,
        description="ISO-8601 UTC timestamp when the manifest was authored.",
    )
    manifest_schema_version: str = Field(default="1.0.0")

    @field_validator("created_utc")
    @classmethod
    def _iso_ish(cls, v: str) -> str:
        # Deterministic, offline check: looks like an ISO-8601 date/datetime.
        if not re.match(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?)?", v):
            raise ValueError("created_utc must be an ISO-8601 date or datetime")
        return v


# ---------------------------------------------------------------------------
# The manifest
# ---------------------------------------------------------------------------

_AGENT_ID_RE = re.compile(r"^[a-z][a-z0-9-]{2,49}$")
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+([-+].+)?$")


class VerificationAgentManifest(BaseModel):
    """Strict manifest describing a single verification agent (prompt pack 4.2).

    This is the input contract for :func:`verification_agent_factory.scaffold`.
    Every field is validated; the model refuses manifests that would produce an
    overclaiming or unsafe agent (e.g. empty prohibited-actions, credentials
    required by default, or public release with an LLM role that has no
    deterministic check).
    """

    model_config = ConfigDict(extra="forbid", use_enum_values=False)

    # Identity
    agent_id: str = Field(
        ...,
        description="Kebab-case unique id, e.g. 'spec-to-sva-agent'.",
    )
    display_name: str = Field(..., min_length=3, max_length=80)
    version: str = Field(..., description="Semantic version, e.g. '0.1.0'.")
    mission: str = Field(
        ...,
        min_length=20,
        max_length=400,
        description="One-sentence mission statement.",
    )
    category: AgentCategory
    owner_role: str = Field(..., min_length=2, max_length=80)
    maturity_level: MaturityLevel

    # Artifacts
    inputs: list[ArtifactKind] = Field(..., min_length=1)
    outputs: list[ArtifactKind] = Field(..., min_length=1)
    supported_design_languages: list[str] = Field(..., min_length=1)

    # Tools and LLM roles
    deterministic_tools: list[str] = Field(..., min_length=1)
    optional_llm_roles: list[LlmRole] = Field(default_factory=list)

    # Safety / authority
    authority_boundary: str = Field(..., min_length=20)
    prohibited_actions: list[str] = Field(..., min_length=1)
    required_human_approvals: list[str] = Field(..., min_length=1)
    claim_policy: ClaimPolicy

    # Validation & evidence
    validation_gates: list[ValidationGate] = Field(..., min_length=1)
    evidence_metrics: list[EvidenceMetric] = Field(..., min_length=1)
    benchmark_manifest: BenchmarkManifest
    reproducibility_requirements: ReproducibilityRequirements = Field(
        default_factory=ReproducibilityRequirements
    )

    # Policy
    data_classification_policy: DataClassificationPolicy = Field(
        default_factory=DataClassificationPolicy
    )
    security_policy: SecurityPolicy = Field(default_factory=SecurityPolicy)
    known_limitations: list[str] = Field(..., min_length=1)

    # Release
    release_status: ReleaseMode
    license: str = Field(default="MIT", min_length=2)

    # Provenance
    provenance: ProvenanceMetadata

    # -- field validators ---------------------------------------------------

    @field_validator("agent_id")
    @classmethod
    def _valid_agent_id(cls, v: str) -> str:
        if not _AGENT_ID_RE.match(v):
            raise ValueError(
                "agent_id must be kebab-case, 3-50 chars, start with a letter "
                "(e.g. 'spec-to-sva-agent')"
            )
        return v

    @field_validator("version")
    @classmethod
    def _valid_version(cls, v: str) -> str:
        if not _SEMVER_RE.match(v):
            raise ValueError("version must be semantic, e.g. '0.1.0'")
        return v

    @field_validator("supported_design_languages", "deterministic_tools")
    @classmethod
    def _non_empty_items(cls, v: list[str]) -> list[str]:
        for item in v:
            if not item or not item.strip():
                raise ValueError("list items must be non-empty strings")
        return v

    # -- cross-field validators --------------------------------------------

    @model_validator(mode="after")
    def _llm_roles_have_checks_for_public(self) -> VerificationAgentManifest:
        """Public agents with LLM roles must pair each with a real check.

        The BUILD_STANDARD requires that the LLM proposes and deterministic
        tools validate. For a public release we enforce that separation.
        """
        if self.release_status == ReleaseMode.PUBLIC:
            for role in self.optional_llm_roles:
                if not role.deterministic_check.strip():
                    raise ValueError(
                        f"LLM role '{role.role}' needs a deterministic_check "
                        "for a public release"
                    )
        return self

    @model_validator(mode="after")
    def _package_name_valid(self) -> VerificationAgentManifest:
        # The derived Python package name must be importable.
        pkg = self.package_name
        if not re.match(r"^[a-z][a-z0-9_]*$", pkg):
            raise ValueError(
                f"agent_id '{self.agent_id}' yields invalid package name '{pkg}'"
            )
        return self

    # -- derived helpers ----------------------------------------------------

    @property
    def package_name(self) -> str:
        """Python package name derived from agent_id (kebab -> snake)."""
        return self.agent_id.replace("-", "_")
