"""Deterministic validation and auditing utilities.

Two concerns live here:

1. Loading + validating a :class:`VerificationAgentManifest` from a JSON/YAML file
   and returning structured, human-readable errors.
2. Auditing a directory tree for content that must never be committed to a public
   repository (secrets, credentials, proprietary / internal markers). This is a
   real regex scan over file contents, not a stub.

Nothing here calls the network or an LLM. All checks are deterministic.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from .models import VerificationAgentManifest

# ---------------------------------------------------------------------------
# Manifest loading / validation
# ---------------------------------------------------------------------------


def _load_mapping(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        try:
            import yaml  # optional dependency
        except ImportError as exc:  # pragma: no cover - depends on env
            raise RuntimeError(
                "PyYAML is required to load YAML manifests; install it or use JSON"
            ) from exc
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("manifest must be a JSON/YAML object at the top level")
    return data


@dataclass
class ManifestValidationResult:
    """Outcome of validating a manifest file."""

    ok: bool
    manifest: VerificationAgentManifest | None = None
    errors: list[str] = field(default_factory=list)


def validate_manifest_file(path: Path) -> ManifestValidationResult:
    """Load and validate a manifest file, returning structured errors.

    Never raises for validation failures; it returns them so the CLI can print a
    clean report and exit non-zero.
    """
    try:
        data = _load_mapping(path)
    except (json.JSONDecodeError, ValueError, RuntimeError) as exc:
        return ManifestValidationResult(ok=False, errors=[f"parse error: {exc}"])

    try:
        manifest = VerificationAgentManifest.model_validate(data)
    except ValidationError as exc:
        errors = []
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"]) or "(root)"
            errors.append(f"{loc}: {err['msg']}")
        return ManifestValidationResult(ok=False, errors=errors)

    return ManifestValidationResult(ok=True, manifest=manifest)


# ---------------------------------------------------------------------------
# Public-release audit (secret / proprietary-name scan)
# ---------------------------------------------------------------------------

# Patterns are intentionally conservative to catch obvious leaks. Each has a
# severity: "blocking" findings should stop a public release; "warning"
# findings need a human look.

_SEVERITY_BLOCKING = "blocking"
_SEVERITY_WARNING = "warning"


@dataclass(frozen=True)
class _Rule:
    name: str
    pattern: re.Pattern[str]
    severity: str
    hint: str


def _build_rules(proprietary_markers: list[str]) -> list[_Rule]:
    rules: list[_Rule] = [
        _Rule(
            "aws_access_key",
            re.compile(r"AKIA[0-9A-Z]{16}"),
            _SEVERITY_BLOCKING,
            "Looks like an AWS access key id.",
        ),
        _Rule(
            "private_key_block",
            re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
            _SEVERITY_BLOCKING,
            "PEM private key material.",
        ),
        _Rule(
            "github_token",
            re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
            _SEVERITY_BLOCKING,
            "Looks like a GitHub token.",
        ),
        _Rule(
            "slack_token",
            re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
            _SEVERITY_BLOCKING,
            "Looks like a Slack token.",
        ),
        _Rule(
            "generic_secret_assignment",
            re.compile(
                r"(?i)\b(?:password|passwd|secret|api[_-]?key|token)\b\s*[:=]\s*"
                r"['\"][^'\"\s]{6,}['\"]"
            ),
            _SEVERITY_BLOCKING,
            "Hard-coded secret/password assignment.",
        ),
        _Rule(
            "private_ssh_url",
            re.compile(r"git@[A-Za-z0-9_.-]+:[A-Za-z0-9_./-]+\.git"),
            _SEVERITY_WARNING,
            "Private git remote URL.",
        ),
        _Rule(
            "internal_hostname",
            re.compile(r"(?i)\b[a-z0-9-]+\.(?:internal|corp|intra|local)\b"),
            _SEVERITY_WARNING,
            "Possible internal hostname.",
        ),
        _Rule(
            "email_address",
            re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
            _SEVERITY_WARNING,
            "Email address; confirm it is safe to publish.",
        ),
    ]
    for marker in proprietary_markers:
        marker = marker.strip()
        if not marker:
            continue
        rules.append(
            _Rule(
                f"proprietary_marker:{marker}",
                re.compile(re.escape(marker), re.IGNORECASE),
                _SEVERITY_BLOCKING,
                f"Proprietary / internal marker '{marker}'.",
            )
        )
    return rules


@dataclass
class AuditFinding:
    """A single audit hit."""

    rule: str
    severity: str
    file: str
    line: int
    excerpt: str
    hint: str


@dataclass
class AuditReport:
    """Aggregate result of a public-release audit."""

    findings: list[AuditFinding] = field(default_factory=list)
    files_scanned: int = 0

    @property
    def blocking(self) -> list[AuditFinding]:
        return [f for f in self.findings if f.severity == _SEVERITY_BLOCKING]

    @property
    def warnings(self) -> list[AuditFinding]:
        return [f for f in self.findings if f.severity == _SEVERITY_WARNING]

    @property
    def clean(self) -> bool:
        return len(self.blocking) == 0


# Directories and file types we never scan (binary / vendored / vcs).
_SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".mypy_cache",
             ".ruff_cache", ".pytest_cache", "dist", "build", ".egg-info"}
_TEXT_SUFFIXES = {
    ".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini",
    ".sv", ".svh", ".v", ".vh", ".cpp", ".hpp", ".c", ".h", ".sh", ".env",
    ".jinja", ".j2", ".rst", "",
}

# Allowlist: example/placeholder emails that are safe and expected in templates.
_ALLOWED_EMAIL_SUBSTRINGS = ("example.com", "noreply", "your-email", "user@host")

# Inline pragma: a line containing this marker is skipped (known-safe fixtures).
_ALLOW_PRAGMA = "audit: allow"


def _is_scannable(path: Path) -> bool:
    if any(part in _SKIP_DIRS or part.endswith(".egg-info") for part in path.parts):
        return False
    if path.suffix.lower() not in _TEXT_SUFFIXES:
        return False
    try:
        return path.stat().st_size < 2_000_000
    except OSError:
        return False


def audit_public_release(
    root: Path,
    proprietary_markers: list[str] | None = None,
    self_file: Path | None = None,
) -> AuditReport:
    """Scan ``root`` recursively for secrets and proprietary markers.

    ``proprietary_markers`` is an optional list of employer/customer/internal
    names to grep for (case-insensitive). ``self_file`` lets a caller exclude the
    audit rule file itself (which necessarily contains the patterns) from the
    scan to avoid self-reports.
    """
    rules = _build_rules(proprietary_markers or [])
    report = AuditReport()
    self_resolved = self_file.resolve() if self_file else None

    for path in sorted(root.rglob("*")):
        if not path.is_file() or not _is_scannable(path):
            continue
        if self_resolved and path.resolve() == self_resolved:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        report.files_scanned += 1
        rel = str(path.relative_to(root))
        for lineno, line in enumerate(text.splitlines(), start=1):
            # Inline pragma to allow known-safe test fixtures / example data.
            if _ALLOW_PRAGMA in line:
                continue
            for rule in rules:
                match = rule.pattern.search(line)
                if not match:
                    continue
                if rule.name == "email_address":
                    lowered = match.group(0).lower()
                    if any(s in lowered for s in _ALLOWED_EMAIL_SUBSTRINGS):
                        continue
                excerpt = line.strip()
                if len(excerpt) > 160:
                    excerpt = excerpt[:157] + "..."
                report.findings.append(
                    AuditFinding(
                        rule=rule.name,
                        severity=rule.severity,
                        file=rel,
                        line=lineno,
                        excerpt=excerpt,
                        hint=rule.hint,
                    )
                )
    return report
