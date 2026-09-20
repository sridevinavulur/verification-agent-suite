"""Small deterministic helpers (hashing, identifier extraction, git sha)."""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Words that appear inside requirement prose but are never RTL signal names.
# Kept small and explicit; grounding still requires Manifest evidence, so a
# stopword miss only costs an "unresolved" flag, never a false mapping.
_STOPWORDS = frozenset(
    {
        "the", "a", "an", "is", "are", "be", "must", "shall", "never", "not",
        "always", "only", "and", "or", "if", "when", "while", "with", "of",
        "to", "in", "on", "for", "that", "this", "it", "its", "any", "all",
        "no", "should", "may", "can", "cannot", "than", "then", "else",
        "assume", "assumes", "cover", "detect", "detected", "value", "state",
        "cycle", "cycles", "within", "mode", "access", "control", "privilege",
        "privileged", "debug", "error", "fault", "read", "write", "data",
        "signal", "output", "input", "register", "bit", "high", "low", "same",
        "two", "one", "match", "matches", "equal", "region", "regions",
        "reset", "clock", "after", "before", "unless", "otherwise", "e.g",
        "i.e", "etc", "from", "into", "by", "as", "at",
    }
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def candidate_identifiers(text: str) -> list[str]:
    """Extract distinct candidate identifier tokens from requirement prose.

    Returns tokens that look like signal names (contain ``_`` or are not common
    English stopwords), preserving first-seen order. This is a *candidate*
    list; grounding still requires Manifest evidence before trusting any of it.
    """
    seen: dict[str, None] = {}
    for tok in _IDENT_RE.findall(text):
        low = tok.lower()
        if "_" in tok or (low not in _STOPWORDS and len(tok) >= 3):
            if tok not in seen:
                seen[tok] = None
    return list(seen)


def git_sha(cwd: str | Path | None = None) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        sha = out.stdout.strip()
        return sha or "UNKNOWN"
    except Exception:
        return "UNKNOWN"
