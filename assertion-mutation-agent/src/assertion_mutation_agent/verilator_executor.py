"""Optional real-simulator executor adapter backed by Verilator.

This adapter implements the same :class:`ExecutorAdapter` interface as
``MockExecutor`` but classifies each mutant by *actually compiling and running*
the mutated RTL together with the SVA property suite under Verilator's native
SystemVerilog assertion support (``--assert``). An assertion that fires on the
mutant (but not on the original design) is treated as real evidence that the
property suite DETECTED the injected defect.

Attribution
-----------
The compile/run/subprocess-orchestration approach here is adapted (cleanly
re-implemented, self-contained) from the reference simulation runner in the
sibling ``spec-to-cov-agent`` project:
``spec-to-cov-agent/veri_forge/sim/{runner.py,verilator.py}``. That reference
drives Verilator + cocotb and parses a JUnit ``results.xml``. This module does
NOT import from spec-to-cov-agent; it re-implements only what is needed and,
instead of cocotb, generates a tiny self-contained SystemVerilog testbench so
the sole external dependency is the ``verilator`` binary.

Graceful degradation (BUILD_STANDARD safety rule)
-------------------------------------------------
- If the ``verilator`` binary is not installed, EVERY mutant is classified
  ERROR (never a fake PASS/DETECTED). The CLI/factory surfaces this clearly.
- A mutant that does not change the source is INVALID (excluded from scoring).
- If the ORIGINAL design does not pass the property suite under this harness,
  the mutant is INCONCLUSIVE (excluded from scoring): we have no trustworthy
  baseline, so we refuse to guess detected/survived.
- A compile failure on the mutant is INVALID (the mutation produced RTL the
  tool cannot elaborate — not meaningful design change evidence).
- A run that exceeds the timeout budget is TIMEOUT; any other tool failure is
  ERROR. Per the standard, TIMEOUT/ERROR/INCONCLUSIVE are NEVER a PASS and are
  never counted as detected.

Scope / non-claims
------------------
This targets the same constrained synthesizable Verilog subset the rest of the
tool supports (single module, simple ports, ``clk``/reset naming). The generated
stimulus is a short deterministic directed sequence, not a full random regression
or a formal proof. A SURVIVED result here means "not detected by this bounded
simulation of this suite", not "the assertion is complete".
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .models import Mutant, MutantResult, MutantStatus, PropertyRef

VERILATOR_BINARY = "verilator"


def verilator_available() -> bool:
    """True iff a ``verilator`` executable is discoverable on PATH."""
    return shutil.which(VERILATOR_BINARY) is not None


# ---------------------------------------------------------------------------
# RTL port parsing (constrained subset)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Port:
    direction: str  # "input" | "output"
    name: str
    width: int  # number of bits (1 for scalar)


_MODULE_RE = re.compile(r"\bmodule\s+([A-Za-z_]\w*)\s*\((.*?)\)\s*;", re.DOTALL)
# Matches:  input wire [7:0] name   /  output reg name  /  input clk
_PORT_RE = re.compile(
    r"\b(input|output|inout)\b"
    r"(?:\s+(?:wire|reg|logic))?"
    r"(?:\s*\[\s*(\d+)\s*:\s*(\d+)\s*\])?"
    r"\s+([A-Za-z_]\w*)"
)


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", " ", text)
    return text


def _parse_module(source: str) -> tuple[str, list[_Port]]:
    """Return (module_name, ports) for the first module in a constrained RTL file."""
    clean = _strip_comments(source)
    m = _MODULE_RE.search(clean)
    if not m:
        raise ValueError("No module declaration found in RTL.")
    module = m.group(1)
    header = m.group(2)
    ports: list[_Port] = []
    for pm in _PORT_RE.finditer(header):
        direction = pm.group(1)
        hi, lo = pm.group(2), pm.group(3)
        if hi is not None and lo is not None:
            width = abs(int(hi) - int(lo)) + 1
        else:
            width = 1
        ports.append(_Port(direction=direction, name=pm.group(4), width=width))
    if not ports:
        raise ValueError("No ports parsed from module header.")
    return module, ports


def _find_clock(ports: list[_Port]) -> str | None:
    for p in ports:
        if p.direction == "input" and p.width == 1 and re.fullmatch(r"clk|clock", p.name):
            return p.name
    return None


def _find_reset(ports: list[_Port]) -> tuple[str, bool] | None:
    """Return (reset_name, active_low) or None. active_low if name ends in _n/n."""
    for p in ports:
        if p.direction != "input" or p.width != 1:
            continue
        n = p.name.lower()
        if "rst" in n or "reset" in n:
            active_low = n.endswith("_n") or n in ("rstn", "resetn")
            return p.name, active_low
    return None


# ---------------------------------------------------------------------------
# Testbench generation
# ---------------------------------------------------------------------------


def _build_testbench(
    module: str,
    ports: list[_Port],
    property_texts: list[str],
    n_cycles: int = 32,
) -> str:
    """Generate a self-contained SV testbench that drives the DUT and binds SVA.

    The SVA property blocks are inlined into a checker module which is ``bind``-ed
    to the DUT so the properties see the DUT's real signals. Verilator's
    ``--assert`` reports a failure (nonzero ``$stop``) when any property fails.
    """
    clk = _find_clock(ports)
    reset = _find_reset(ports)

    decls: list[str] = []
    conns: list[str] = []
    driven_inputs: list[_Port] = []
    for p in ports:
        kind = "logic" if p.width == 1 else f"logic [{p.width - 1}:0]"
        decls.append(f"    {kind} {p.name};")
        conns.append(f".{p.name}({p.name})")
        if p.direction == "input" and p.name != clk and (
            reset is None or p.name != reset[0]
        ):
            driven_inputs.append(p)

    # Deterministic pseudo-random stimulus (linear congruential, seeded).
    stim_lines: list[str] = []
    lcg = "        lfsr = lfsr * 32'h0019660D + 32'h3C6EF35F;"
    for i, p in enumerate(driven_inputs):
        mask = (1 << p.width) - 1
        lo = (i * 3) % 24
        hi = lo + p.width - 1
        stim_lines.append(
            f"        {p.name} <= lfsr[{hi}:{lo}] & {p.width}'h{mask:x};"
        )

    reset_assign_active = ""
    reset_assign_release = ""
    if reset is not None:
        rname, active_low = reset
        if active_low:
            reset_assign_active = f"        {rname} = 1'b0;"
            reset_assign_release = f"        {rname} = 1'b1;"
        else:
            reset_assign_active = f"        {rname} = 1'b1;"
            reset_assign_release = f"        {rname} = 1'b0;"

    clk_gen = ""
    if clk is not None:
        clk_gen = f"    always #5 {clk} = ~{clk};\n"

    # Checker module holding the SVA properties, bound into the DUT. Each
    # ``property NAME ... endproperty`` block gets a matching ``assert property``
    # so a violation actually fires; inline ``label : assert property (...)``
    # blocks already assert themselves.
    prop_name_re = re.compile(r"\bproperty\s+([A-Za-z_]\w*)")
    body_parts: list[str] = []
    for i, text in enumerate(property_texts):
        body_parts.append(text)
        for pm in prop_name_re.finditer(text):
            pname = pm.group(1)
            body_parts.append(f"    amm_a_{i}_{pname}: assert property ({pname});")
    checker_body = "\n".join(body_parts)
    # Collect the checker's port list from DUT ports so property signals resolve.
    checker_ports = ", ".join(
        f"input {'logic' if p.width == 1 else f'logic [{p.width - 1}:0]'} {p.name}"
        for p in ports
    )
    checker_conns = ", ".join(f".{p.name}({p.name})" for p in ports)

    init_driven = "\n".join(
        f"        {p.name} = '0;" for p in driven_inputs
    )

    tb = f"""\
// AUTO-GENERATED self-contained SVA harness (assertion-mutation-agent).
// Adapted in spirit from spec-to-cov-agent/veri_forge/sim (no import thereof).

module amm_checker ({checker_ports});
{checker_body}
endmodule

bind {module} amm_checker amm_checker_i ({checker_conns});

module amm_tb;
{chr(10).join(decls)}

    integer amm_i;
    reg [31:0] lfsr;

{clk_gen}
    initial begin
        lfsr = 32'h1234ABCD;
        {clk + " = 1'b0;" if clk else ""}
{init_driven}
{reset_assign_active}
        // Hold reset for a few cycles.
        repeat (4) @(posedge {clk if clk else "amm_i"});
{reset_assign_release}

        for (amm_i = 0; amm_i < {n_cycles}; amm_i = amm_i + 1) begin
{lcg}
{chr(10).join(stim_lines)}
            @(posedge {clk if clk else "amm_i"});
        end
        $finish;
    end

    {module} dut ({", ".join(conns)});
endmodule
"""
    return tb


# ---------------------------------------------------------------------------
# Compile + run
# ---------------------------------------------------------------------------


@dataclass
class _RunOutcome:
    compiled: bool
    ran: bool
    assertion_failed: bool
    timed_out: bool
    tool_error: bool
    detail: str


def _compile_and_run(
    rtl_source: str,
    property_texts: list[str],
    work_dir: Path,
    timeout_s: int,
) -> _RunOutcome:
    """Compile the RTL + SVA harness with Verilator --binary --assert and run it."""
    verilator = shutil.which(VERILATOR_BINARY)
    if verilator is None:  # pragma: no cover - guarded by caller
        return _RunOutcome(False, False, False, False, True, "verilator not found")

    try:
        module, ports = _parse_module(rtl_source)
    except ValueError as e:
        return _RunOutcome(False, False, False, False, True, f"port parse failed: {e}")

    rtl_path = work_dir / f"{module}.sv"
    rtl_path.write_text(rtl_source, encoding="utf-8")
    tb_path = work_dir / "amm_tb.sv"
    tb_path.write_text(
        _build_testbench(module, ports, property_texts), encoding="utf-8"
    )

    obj_dir = work_dir / "obj_dir"
    # Compile to a native binary with assertions enabled.
    compile_cmd = [
        verilator,
        "--binary",
        "--assert",
        "--timing",
        "-Wno-fatal",  # lint warnings must not abort mutant elaboration
        "--top-module",
        "amm_tb",
        "-Mdir",
        str(obj_dir),
        str(rtl_path),
        str(tb_path),
    ]
    try:
        cp = subprocess.run(
            compile_cmd,
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return _RunOutcome(False, False, False, True, False, "compile timeout")
    except OSError as e:  # pragma: no cover - environment dependent
        return _RunOutcome(False, False, False, False, True, f"compile exec error: {e}")

    if cp.returncode != 0:
        return _RunOutcome(
            compiled=False,
            ran=False,
            assertion_failed=False,
            timed_out=False,
            tool_error=False,
            detail=f"compile failed (rc={cp.returncode}): {cp.stderr[-500:]}",
        )

    sim_bin = obj_dir / "Vamm_tb"
    if not sim_bin.exists():
        return _RunOutcome(True, False, False, False, True, "sim binary not produced")

    try:
        rp = subprocess.run(
            [str(sim_bin)],
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return _RunOutcome(True, True, False, True, False, "run timeout")
    except OSError as e:  # pragma: no cover - environment dependent
        return _RunOutcome(True, True, False, False, True, f"run exec error: {e}")

    combined = (rp.stdout + "\n" + rp.stderr).lower()
    # Verilator emits "%Error: ...Assertion failed" and a nonzero exit on failure.
    assertion_failed = (
        "assertion failed" in combined
        or "assert failed" in combined
        or rp.returncode != 0
    )
    return _RunOutcome(
        compiled=True,
        ran=True,
        assertion_failed=assertion_failed,
        timed_out=False,
        tool_error=False,
        detail=f"run rc={rp.returncode}",
    )


class VerilatorExecutor:
    """Real-simulator executor: compiles + runs each mutant under Verilator.

    See module docstring for the classification contract and graceful-degradation
    guarantees. This adapter satisfies the same :class:`ExecutorAdapter` Protocol
    as :class:`MockExecutor`.
    """

    name = "verilator"

    def __init__(self, timeout_s: int = 120) -> None:
        self.timeout_s = timeout_s
        # Cache baseline (original design) pass/fail per property-suite signature
        # so we do not re-run the original for every mutant.
        self._baseline_ok: dict[str, bool] = {}

    def _baseline_passes(
        self, original_source: str, property_texts: list[str]
    ) -> bool:
        key = original_source + "\x00" + "\x00".join(property_texts)
        if key in self._baseline_ok:
            return self._baseline_ok[key]
        with tempfile.TemporaryDirectory(prefix="amm_base_") as td:
            outcome = _compile_and_run(
                original_source, property_texts, Path(td), self.timeout_s
            )
        ok = outcome.compiled and outcome.ran and not outcome.assertion_failed
        self._baseline_ok[key] = ok
        return ok

    def classify(
        self, mutant: Mutant, original_source: str, properties: list[PropertyRef]
    ) -> MutantResult:
        # No-op mutation -> INVALID, exactly like the mock executor.
        if mutant.mutated_source == original_source:
            return MutantResult(
                mutant_id=mutant.mutant_id,
                operator=mutant.operator,
                status=MutantStatus.INVALID,
                detail="Mutant did not change the source (no-op mutation).",
                executor=self.name,
            )

        if not verilator_available():
            # Graceful degradation: never a fake pass.
            return MutantResult(
                mutant_id=mutant.mutant_id,
                operator=mutant.operator,
                status=MutantStatus.ERROR,
                detail="verilator binary not found; cannot execute mutant.",
                executor=self.name,
            )

        property_texts = [p.text for p in properties if p.text.strip()]
        if not property_texts:
            return MutantResult(
                mutant_id=mutant.mutant_id,
                operator=mutant.operator,
                status=MutantStatus.INCONCLUSIVE,
                detail="No SVA property text available to bind; observability unknown.",
                executor=self.name,
            )

        # Baseline: the original design MUST pass the suite, else we cannot trust
        # a mutant failure as detection evidence.
        if not self._baseline_passes(original_source, property_texts):
            return MutantResult(
                mutant_id=mutant.mutant_id,
                operator=mutant.operator,
                status=MutantStatus.INCONCLUSIVE,
                detail=(
                    "Original design did not pass the SVA harness; no trustworthy "
                    "baseline to attribute mutant failures to the mutation."
                ),
                executor=self.name,
            )

        with tempfile.TemporaryDirectory(prefix="amm_mut_") as td:
            outcome = _compile_and_run(
                mutant.mutated_source, property_texts, Path(td), self.timeout_s
            )

        if outcome.timed_out:
            return MutantResult(
                mutant_id=mutant.mutant_id,
                operator=mutant.operator,
                status=MutantStatus.TIMEOUT,
                detail=outcome.detail,
                executor=self.name,
            )
        if outcome.tool_error:
            return MutantResult(
                mutant_id=mutant.mutant_id,
                operator=mutant.operator,
                status=MutantStatus.ERROR,
                detail=outcome.detail,
                executor=self.name,
            )
        if not outcome.compiled:
            # Mutant does not elaborate -> not a meaningful design change we can
            # score. Treat as INVALID (excluded from scoring), never a PASS.
            return MutantResult(
                mutant_id=mutant.mutant_id,
                operator=mutant.operator,
                status=MutantStatus.INVALID,
                detail=f"Mutant failed to compile: {outcome.detail}",
                executor=self.name,
            )
        if outcome.assertion_failed:
            detected_by = sorted(p.name for p in properties if p.text.strip())
            return MutantResult(
                mutant_id=mutant.mutant_id,
                operator=mutant.operator,
                status=MutantStatus.DETECTED,
                detected_by=detected_by,
                detail="At least one SVA property failed on the mutated design.",
                executor=self.name,
            )
        return MutantResult(
            mutant_id=mutant.mutant_id,
            operator=mutant.operator,
            status=MutantStatus.SURVIVED,
            detail=(
                "No SVA property failed on the mutated design under the bounded "
                "harness; undetected mutation requiring investigation."
            ),
            executor=self.name,
        )
