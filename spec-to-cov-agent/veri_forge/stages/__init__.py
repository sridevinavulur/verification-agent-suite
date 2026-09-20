"""veri-forge pipeline stages."""
from .s01_spec_parser import SpecParser
from .s02_rtl_designer import RtlDesigner
from .s03_lint_runner import LintRunner
from .s04_rtl_reviewer import RtlReviewer
from .s05_property_gen import PropertyGen
from .s06_formal import Formal
from .s07_lec import Lec
from .s08_testplan_gen import TestplanGen
from .s09_ref_model import RefModelGen
from .s10_uvm_vip import UvmVipGen
from .s11_cocotb_vip import CocotbVipGen
from .s12_test_gen import TestGen
from .s13_simulation import Simulation
from .s14_fsdb_analyzer import FsdbAnalyzer
from .s15_debug_analyzer import DebugAnalyzer
from .s16_coverage_closure import CoverageClosureStage

STAGE_MAP = {
    1:  SpecParser,
    2:  RtlDesigner,
    3:  LintRunner,
    4:  RtlReviewer,
    5:  PropertyGen,
    6:  Formal,
    7:  Lec,
    8:  TestplanGen,
    9:  RefModelGen,
    10: UvmVipGen,
    11: CocotbVipGen,
    12: TestGen,
    13: Simulation,
    14: FsdbAnalyzer,
    15: DebugAnalyzer,
    16: CoverageClosureStage,
}
