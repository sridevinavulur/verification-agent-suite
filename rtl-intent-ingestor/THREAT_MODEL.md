# Threat Model

This is a research prototype for public RTL. The risks below are about
**incorrect or overclaimed analysis** and **data leakage**, not adversarial
software security. Each risk lists how the tool mitigates it and the residual
gap a reviewer must keep in mind.

## 1. Hallucination / silent invention

**Risk:** presenting a signal, width, clock, or reset that does not exist in the
source, or silently guessing semantics.

**Mitigation:**
- No LLM in v0.1 — nothing is generated, only extracted.
- The parser never invents names; unrecognized regions become
  `UnresolvedConstruct` entries, visible in the manifest.
- Widths/parameter values are carried as **verbatim source text** (e.g.
  `WIDTH-1`), never evaluated or fabricated.

**Residual gap:** the parser can mis-attach a token in malformed input; such
cases should surface as unresolved constructs or an obviously wrong count.

## 2. Unsafe / overclaimed assumptions

**Risk:** treating heuristic clock/reset detection as ground truth, or calling a
structural "register" a proven state element.

**Mitigation:**
- Clock/reset candidates carry a bounded `confidence` in `[0,1]` and an explicit
  `rationale` list; the Markdown report labels the whole section *(heuristic)*.
- `Register`, `ClockCandidate`, `ResetCandidate` docstrings state they are
  structural/heuristic, not formal.
- README has an explicit **non-claims** section.

**Residual gap:** a downstream consumer could ignore the confidence field.
Consumers must gate on it and on human review.

## 3. Incomplete coverage presented as complete

**Risk:** a design uses constructs outside the subset and the user assumes full
extraction.

**Mitigation:**
- `Manifest.unresolved` lists every unsupported construct with a location.
- `ParserInfo.supported_constructs` / `unsupported_constructs` are embedded in
  every manifest and rendered in the report.
- The CLI prints an `unresolved construct(s)` note to stderr.

## 4. Data leakage

**Risk:** committing proprietary RTL, customer/employer names, internal tool
names, credentials, or private paths.

**Mitigation:**
- Only public toy RTL is bundled (`examples/`).
- Input file **hashes** are recorded, not file contents, in provenance.
- `SECURITY.md` and the data-policy README section state the public-only rule.
- `.gitignore` excludes local venvs and scratch outputs.

**Residual gap:** the tool cannot stop a user pointing it at proprietary RTL and
committing the resulting manifest, which would contain signal names and source
paths. Run a release audit before publishing any generated manifest.

## 5. Reproducibility

**Risk:** non-deterministic output undermines golden tests and provenance.

**Mitigation:**
- Deterministic ordering + `sort_keys` JSON (see ARCHITECTURE.md → Determinism).
- Provenance records tool version, schema version, input hashes, command, and a
  git-SHA placeholder for CI/release tooling to fill.
- Golden tests assert byte-for-byte stability and Pydantic round-trip.

## 6. Version / contract drift

**Risk:** the manifest layout changes and silently breaks downstream tools.

**Mitigation:** `MANIFEST_SCHEMA_VERSION` is embedded in every manifest and must
be bumped on incompatible changes; the exported JSON Schema is committed.
