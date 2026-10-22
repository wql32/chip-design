from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from test_rtl_priority_repairs import ASSETS, ROOT, IVL_LIB, IVERILOG, VVP, pyslang, check_elaboration, check_simulation


def bench_cases() -> list[tuple[str, dict[str, int], list[Path]]]:
    cases = [("tb_fifos", {"DEPTH": depth}, [ASSETS / "2w1r_fifo/2w1r_fifo.v", ASSETS / "basic_fifo/basic_fifo.v"]) for depth in (1, 2, 3, 8, 9)]
    cases += [("tb_storage", {"DEPTH": depth, "PIN": pin, "POUT": pout}, [ASSETS / "ff_cam/ff_cam.v", ASSETS / "ff_array/ff_arrary.v"]) for depth in (1, 3, 9) for pin in (0, 1) for pout in (0, 1)]
    cases += [("tb_pointer_pool", {"N": n}, [ASSETS / "free_ptr_mng/free_ptr_mng.v"]) for n in (1, 2, 3, 9, 64, 384)]
    cases += [("tb_divider", {"FACTOR": factor, "MODE": mode}, [ASSETS / "clk_divider/clk_divider.v"]) for factor, mode in ((2, 0), (4, 0), (8, 0), (3, 1), (5, 1), (7, 1), (9, 1), (1, 1), (3, 0), (2, 1), (5, 2))]
    return cases


@unittest.skipIf(pyslang is None, "pyslang unavailable")
class RemainingRtlCompileTests(unittest.TestCase):
    def test_actual_rtl_and_benches_elaborate(self) -> None:
        for top, parameters, sources in bench_cases():
            with self.subTest(top=top, parameters=parameters):
                check_elaboration(self, top, parameters, sources)


@unittest.skipUnless(IVERILOG and VVP, "Icarus Verilog/vvp unavailable")
class RemainingRtlSimulationTests(unittest.TestCase):
    def test_self_checking_rtl_benches(self) -> None:
        with tempfile.TemporaryDirectory(prefix=".rtl_sim_", dir=ROOT) as directory:
            for top, parameters, sources in bench_cases():
                with self.subTest(top=top, parameters=parameters):
                    check_simulation(self, top, parameters, sources, Path(directory))


if __name__ == "__main__":
    unittest.main()
