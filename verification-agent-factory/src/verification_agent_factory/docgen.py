"""Turn a validated manifest into Markdown documentation sections.

Deterministic string rendering only. The same manifest always yields byte-for-byte
identical output, which is what the golden tests rely on.
"""

from __future__ import annotations

from .models import VerificationAgentManifest


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items) if items else "- (none)"


def render_claims_section(m: VerificationAgentManifest) -> str:
    """Render the mandated explicit-claim strings (prompt pack 4.2)."""
    c = m.claim_policy
    return "\n".join(
        [
            "## Claims policy",
            "",
            f"- **This agent may claim** {c.may_claim}",
            f"- **This agent must not claim** {c.must_not_claim}",
            f"- **A passing result means** {c.passing_result_means}",
            f"- **A timeout or unknown result means** {c.timeout_or_unknown_means}",
            f"- **Human review is required when** {c.human_review_required_when}",
        ]
    )


def render_authority_section(m: VerificationAgentManifest) -> str:
    return "\n".join(
        [
            "## Authority boundary",
            "",
            m.authority_boundary,
            "",
            "### Prohibited actions",
            "",
            _bullets(m.prohibited_actions),
            "",
            "### Requires human approval",
            "",
            _bullets(m.required_human_approvals),
        ]
    )


def render_validation_section(m: VerificationAgentManifest) -> str:
    gates = [
        f"- **{g.name}** ({'blocking' if g.blocking else 'non-blocking'}): {g.description}"
        for g in m.validation_gates
    ]
    metrics = [
        f"- **{e.name}**: {e.description} (_measured: {e.how_measured}_)"
        for e in m.evidence_metrics
    ]
    return "\n".join(
        [
            "## Validation gates",
            "",
            "\n".join(gates),
            "",
            "## Evidence metrics",
            "",
            "\n".join(metrics),
        ]
    )


def render_llm_section(m: VerificationAgentManifest) -> str:
    if not m.optional_llm_roles:
        return "\n".join(
            [
                "## LLM roles",
                "",
                "This agent uses **no LLM**; all logic is deterministic.",
            ]
        )
    rows = [
        f"- LLM proposes: {r.role} → validated by: {r.deterministic_check}"
        for r in m.optional_llm_roles
    ]
    return "\n".join(
        [
            "## LLM roles",
            "",
            "The LLM only *proposes*; deterministic tools validate every output.",
            "",
            "\n".join(rows),
        ]
    )


def render_overview_section(m: VerificationAgentManifest) -> str:
    inputs = ", ".join(v.value for v in m.inputs)
    outputs = ", ".join(v.value for v in m.outputs)
    langs = ", ".join(m.supported_design_languages)
    tools = ", ".join(m.deterministic_tools)
    return "\n".join(
        [
            f"# {m.display_name}",
            "",
            f"> {m.mission}",
            "",
            f"- **Agent id:** `{m.agent_id}`",
            f"- **Version:** {m.version}",
            f"- **Category:** {m.category.value}",
            f"- **Owner role:** {m.owner_role}",
            f"- **Maturity:** {m.maturity_level.value}",
            f"- **Release status:** {m.release_status.value}",
            f"- **License:** {m.license}",
            "",
            f"- **Inputs:** {inputs}",
            f"- **Outputs:** {outputs}",
            f"- **Supported design languages:** {langs}",
            f"- **Deterministic tools:** {tools}",
        ]
    )


def render_limitations_section(m: VerificationAgentManifest) -> str:
    return "\n".join(
        [
            "## Known limitations and non-claims",
            "",
            _bullets(m.known_limitations),
        ]
    )


def render_benchmark_section(m: VerificationAgentManifest) -> str:
    b = m.benchmark_manifest
    return "\n".join(
        [
            "## Benchmark",
            "",
            f"- **Name:** {b.name}",
            f"- **Description:** {b.description}",
            f"- **Public source:** {b.public_source}",
            f"- **License:** {b.license}",
        ]
    )


def render_data_policy_section(m: VerificationAgentManifest) -> str:
    d = m.data_classification_policy
    return "\n".join(
        [
            "## Data classification policy",
            "",
            f"Allowed inputs: {d.allowed_inputs}",
            "",
            "**Must never be committed:**",
            "",
            _bullets(d.must_not_commit),
        ]
    )


def render_readme(m: VerificationAgentManifest) -> str:
    """Render a full README body from the manifest."""
    sections = [
        render_overview_section(m),
        render_claims_section(m),
        render_authority_section(m),
        render_llm_section(m),
        render_validation_section(m),
        render_benchmark_section(m),
        render_data_policy_section(m),
        render_limitations_section(m),
    ]
    body = "\n\n".join(sections)
    return body + "\n"
