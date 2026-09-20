"""Contract generator: ContractRequest + RtlManifest -> ProtocolContract.

Orchestrates grounding + the protocol template into a full, reviewable contract.
All safety flags (unbound required roles, assume-on-output, unknown reset
polarity) surface as warnings and checklist items; nothing is silently dropped.
"""

from __future__ import annotations

from . import templates
from .grounding import (
    require_signal,
    resolve_clock,
    resolve_reset,
)
from .models import (
    ClockResetMapping,
    ContractProperty,
    ContractRequest,
    GroundedSymbol,
    PropertyDependency,
    ProtocolContract,
    ProtocolKind,
    Provenance,
    ResetPolarity,
    ResetSync,
    RtlManifest,
    Severity,
    SignalRole,
    Warning,
)

_LIMITATIONS = [
    "Every property is a CANDIDATE for human review. Nothing here is verified, "
    "proven, or signoff-quality. No formal tool or simulator is run.",
    "Candidate SVA is rendered deterministically and is intended to be compiled "
    "OFFLINE by a separate tool; syntactic acceptance would not imply semantic "
    "correctness.",
    "Role -> signal bindings come from the request; the tool does not infer which "
    "signal plays which protocol role.",
    "Clock/reset polarity is taken from the request or the manifest candidates and "
    "is NEVER inferred by name. Unknown polarity blocks polarity-dependent "
    "properties instead of guessing.",
    "Structural checks (combinational deadlock, real synchronizer presence, arbiter "
    "fairness, exact width matching) are NOT performed.",
    "FIFO/credit contracts require explicit depth/max_credits and a count/credit "
    "signal to bound occupancy; without them, occupancy bounds are omitted rather "
    "than invented.",
]

_RESET_BEHAVIOR = {
    (ResetPolarity.ACTIVE_LOW, ResetSync.ASYNCHRONOUS):
        "Asynchronous, active-low reset (rst_n): registers reset when rst_n==0; "
        "properties use `disable iff (!rst)`.",
    (ResetPolarity.ACTIVE_LOW, ResetSync.SYNCHRONOUS):
        "Synchronous, active-low reset: registers reset on clock edge when "
        "reset==0; properties use `disable iff (!rst)`.",
    (ResetPolarity.ACTIVE_HIGH, ResetSync.ASYNCHRONOUS):
        "Asynchronous, active-high reset: registers reset when reset==1; "
        "properties use `disable iff (rst)`.",
    (ResetPolarity.ACTIVE_HIGH, ResetSync.SYNCHRONOUS):
        "Synchronous, active-high reset: registers reset on clock edge when "
        "reset==1; properties use `disable iff (rst)`.",
}


def _reset_behavior(polarity: ResetPolarity, sync: ResetSync, reset: str | None) -> str:
    if reset is None:
        return "No reset resolved: reset behavior is UNSPECIFIED and must be reviewed."
    key = (polarity, sync)
    if key in _RESET_BEHAVIOR:
        return _RESET_BEHAVIOR[key]
    return (
        f"Reset {reset!r} resolved with polarity={polarity.value}, "
        f"sync={sync.value}: reset behavior is UNDER-SPECIFIED and must be reviewed. "
        "Polarity-dependent properties are skipped when polarity is unknown."
    )


def generate_contract(
    request: ContractRequest,
    manifest: RtlManifest,
    *,
    git_sha: str = "UNKNOWN",
    command: str | None = None,
) -> ProtocolContract:
    module = manifest.module(request.module)
    if module is None:
        raise ValueError(
            f"module {request.module!r} not found in manifest "
            f"(have: {[m.name for m in manifest.modules]})"
        )

    proto = request.protocol.value
    req_roles, opt_roles = templates.REQUIRED_ROLES[proto]

    warnings: list[Warning] = []
    signal_roles: list[SignalRole] = []
    grounded: dict[str, GroundedSymbol] = {}

    # Ground required roles.
    for role in req_roles:
        name = request.roles.get(role)
        if name is None:
            warnings.append(
                Warning(
                    code="missing_required_role",
                    message=f"required role {role!r} not bound for protocol {proto}",
                    severity=Severity.ERROR,
                )
            )
            continue
        sym = require_signal(module, name)
        grounded[role] = sym
        signal_roles.append(SignalRole(role=role, symbol=sym, required=True))

    # Ground optional roles that were provided.
    for role in opt_roles:
        name = request.roles.get(role)
        if name is None:
            continue
        sym = require_signal(module, name)
        grounded[role] = sym
        signal_roles.append(SignalRole(role=role, symbol=sym, required=False))

    # Warn about unknown role names in the request.
    known = set(req_roles) | set(opt_roles)
    for role in request.roles:
        if role not in known:
            warnings.append(
                Warning(
                    code="unknown_role",
                    message=f"role {role!r} is not defined for protocol {proto}; "
                    "ignored",
                    severity=Severity.WARNING,
                )
            )

    # Clock / reset.
    clock_sym = resolve_clock(module, request.clock)
    reset_sym, polarity, sync = resolve_reset(
        module, request.reset, request.reset_polarity
    )
    if clock_sym is None:
        warnings.append(
            Warning(
                code="no_clock",
                message="no clock resolved; temporal properties cannot be rendered",
                severity=Severity.ERROR,
            )
        )

    clock_reset = ClockResetMapping(
        clock=clock_sym,
        reset=reset_sym,
        reset_polarity=polarity,
        reset_sync=sync,
        reset_behavior=_reset_behavior(
            polarity, sync, reset_sym.name if reset_sym else None
        ),
    )

    contract = ProtocolContract(
        contract_id=f"{request.module}__{proto}"
        + (f"__{request.instance_label}" if request.instance_label else ""),
        protocol=request.protocol,
        module=request.module,
        instance_label=request.instance_label,
        signal_roles=signal_roles,
        clock_reset=clock_reset,
        warnings=warnings,
        limitations=list(_LIMITATIONS),
        provenance=Provenance(
            git_sha=git_sha,
            command=command,
            manifest_module=request.module,
            protocol=request.protocol,
        ),
    )

    # If required roles or clock are missing, return the partial contract with
    # warnings rather than fabricate properties.
    have_all_required = all(role in grounded for role in req_roles)
    if not have_all_required or clock_sym is None:
        contract.checklist.append(
            templates.ChecklistItem(
                id="blocking_inputs_missing",
                question="Blocking issues prevent property generation (see warnings): "
                "resolve required roles and clock before review.",
                severity=Severity.ERROR,
                auto_status="FAIL",
            )
        )
        return contract

    ctx = templates._Ctx(
        module=request.module,
        clock=clock_sym.name,
        reset=reset_sym.name if reset_sym else None,
        reset_polarity=polarity,
        roles=grounded,
        depth=request.depth,
        max_credits=request.max_credits,
        min_delay=request.min_delay,
        max_delay=request.max_delay,
    )

    result = templates.GENERATORS[proto](ctx)

    contract.assumptions = result.assumptions
    contract.guarantees = result.guarantees
    contract.properties = result.properties
    contract.negative_scenarios = result.negatives
    contract.checklist.extend(result.checklist)
    contract.warnings.extend(ctx.warnings)
    contract.warnings.extend(result.warnings)

    # Dependency map derived from properties' depends_on.
    contract.dependencies = _build_dependencies(result.properties)

    return contract


def _build_dependencies(props: list[ContractProperty]) -> list[PropertyDependency]:
    deps: list[PropertyDependency] = []
    for p in props:
        if p.depends_on:
            deps.append(
                PropertyDependency(
                    property_name=p.name,
                    depends_on=list(p.depends_on),
                    rationale="consequent property assumes the antecedent property "
                    "holds (e.g. latency guarantee assumes no-spurious guarantee).",
                )
            )
    return deps


def _all_referenced_grounded(contract: ProtocolContract) -> bool:
    """Invariant check: every property references only grounded symbols
    (non-empty symbol_id). Used by tests to enforce the grounding guarantee."""
    for p in contract.properties:
        for s in p.referenced_symbols:
            if not s.symbol_id:
                return False
    return True


# Convenience for tests / other tools.
def blocking_warnings(contract: ProtocolContract) -> list[Warning]:
    return [w for w in contract.warnings if w.severity == Severity.ERROR]


PROTOCOL_KINDS = [k.value for k in ProtocolKind]
