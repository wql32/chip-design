"""Cycle/expression checks, plus optional execution of the actual RTL with Icarus.

The Python models do not model metastability and are not RTL simulation.
"""
from __future__ import annotations

import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import deque
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "sysip_hub/assets/wql32_rtl"
LOCAL_TOOLS = ROOT / ".rtl_tools/python"
if (LOCAL_TOOLS / "pyslang").is_dir():
    sys.path.insert(0, str(LOCAL_TOOLS))
try:
    import pyslang
except ModuleNotFoundError as exc:
    if exc.name != "pyslang":
        raise
    pyslang = None


def simulator_tools() -> tuple[str | None, str | None, Path | None]:
    local = ROOT / ".rtl_tools/iverilog/app"
    if (local / "bin/iverilog.exe").is_file() and (local / "bin/vvp.exe").is_file():
        return str(local / "bin/iverilog.exe"), str(local / "bin/vvp.exe"), local / "lib/ivl"
    return shutil.which("iverilog"), shutil.which("vvp"), None


IVERILOG, VVP, IVL_LIB = simulator_tools()


def check_elaboration(test: unittest.TestCase, top: str, parameters: dict[str, int], sources: list[Path]) -> None:
    options = pyslang.ast.CompilationOptions()
    options.topModules = {top}
    options.paramOverrides = [f"{key}={value}" for key, value in parameters.items()]
    options.defaultTimeScale = pyslang.TimeScale.fromString("1ns/1ps")
    compilation = pyslang.ast.Compilation(pyslang.Bag([options]))
    paths = [sources[0].parent / "tb" / f"{top}.sv", *sources]
    for path in paths:
        compilation.addSyntaxTree(pyslang.syntax.SyntaxTree.fromText(path.read_text(encoding="utf-8"), name=path.name))
    root = compilation.getRoot()
    errors = [diag for diag in compilation.getAllDiagnostics() if diag.isError()]
    test.assertFalse(errors, pyslang.DiagnosticEngine.reportAll(compilation.sourceManager, errors))
    test.assertEqual(len(root.topInstances), 1)
    for key, value in parameters.items():
        test.assertEqual(int(root.topInstances[0].body.find(key).value.value), value)


def check_simulation(test: unittest.TestCase, top: str, parameters: dict[str, int], sources: list[Path], directory: Path) -> None:
    # Relative ASCII filenames also work with MinGW tools in Unicode workspaces.
    output = (directory / "bench.vvp").relative_to(ROOT).as_posix()
    command = [str(IVERILOG), "-g2012", "-Wall", "-s", top, "-o", output]
    if IVL_LIB:
        command += ["-B", str(IVL_LIB.relative_to(ROOT))]
    command += [f"-P{top}.{key}={value}" for key, value in parameters.items()]
    command += [(sources[0].parent / "tb" / f"{top}.sv").relative_to(ROOT).as_posix()]
    command += [path.relative_to(ROOT).as_posix() for path in sources]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
    test.assertEqual(result.returncode, 0, result.stdout + result.stderr)
    command = [str(VVP)]
    if IVL_LIB:
        command += ["-M", str(IVL_LIB.relative_to(ROOT))]
    result = subprocess.run([*command, output], cwd=ROOT, capture_output=True, text=True, timeout=30)
    test.assertEqual(result.returncode, 0, result.stdout + result.stderr)
    test.assertIn("PASS", result.stdout)


def bench_cases() -> list[tuple[str, dict[str, int], list[Path]]]:
    cases = [("tb_encoder", {"WIDTH": width}, [ASSETS / "onehot2bin/onehot2bin.v", ASSETS / "find_1st_one/find_1st_one.v"]) for width in (1, 2, 3, 8, 9, 16, 253, 256, 257, 384, 512)]
    cases += [("tb_scheduler", {"N": n}, [ASSETS / "rr_sch/rr_sch.v"]) for n in (1, 3, 5, 64)]
    cases += [("tb_handshake", {"SRC_HALF": src, "DST_HALF": dst, "DST_PHASE": phase}, [ASSETS / "handshake_sync/handshake_sync.v"]) for src, dst, phase in ((3, 11, 0), (13, 2, 1), (5, 5, 0), (5, 5, 2))]
    return cases


def encode_bit_planes(bitmap: int, width: int, bits: int) -> int:
    result = 0
    for binary_idx in range(bits):
        plane = sum(((bitmap >> idx) & 1) << idx for idx in range(width) if (idx >> binary_idx) & 1)
        result |= bool(plane) << binary_idx
    return result


def prefix_masks(request: int, width: int) -> int:
    return sum(bool(request & ((1 << idx) - 1)) << idx for idx in range(width))


def scheduler_step(request: int, width: int, mask: int, enable: bool, reset_n: bool = True) -> tuple[int, int]:
    if not reset_n:
        return 0, 0
    if not enable or not request:
        return 0, mask
    masked = request & mask
    selected = masked if masked else request
    prefix = prefix_masks(selected, width)
    return selected & ~prefix, prefix


class HandshakeModel:
    def __init__(self) -> None:
        self.state = dict.fromkeys(("req", "data", "req0", "req1", "reqd", "ack", "ack0", "ack1", "valid", "out"), 0)

    def tick(self, src_edge: bool, dst_edge: bool, valid: bool, data: int, reset_n: bool = True) -> tuple[bool, int | None]:
        old = self.state.copy()
        new = old.copy()
        if not reset_n:
            self.state = dict.fromkeys(old, 0)
            return False, None
        fire = bool(src_edge and valid and not old["req"] and not old["ack1"])
        received = old["out"] if dst_edge and old["valid"] else None
        if src_edge:
            new["ack0"], new["ack1"] = old["ack"], old["ack0"]
            if fire:
                new["data"], new["req"] = data, 1
            elif old["ack1"]:
                new["req"] = 0
        if dst_edge:
            new["req0"], new["req1"], new["reqd"] = old["req"], old["req0"], old["req1"]
            pulse = old["req1"] and not old["reqd"]
            new["valid"] = int(pulse)
            if pulse:
                new["out"], new["ack"] = old["data"], 1
            elif not old["req1"]:
                new["ack"] = 0
        self.state = new
        return fire, received


class PriorityRtlModelTests(unittest.TestCase):
    def test_encoder_zero_and_every_onehot_position(self) -> None:
        for width in (1, 2, 3, 7, 8, 9, 16, 31, 64, 253, 256, 257, 384, 512):
            bits = max(1, (width - 1).bit_length())
            for output_bits in (bits, bits + 2):
                self.assertEqual(encode_bit_planes(0, width, output_bits), 0)
                for idx in range(width):
                    self.assertEqual(encode_bit_planes(1 << idx, width, output_bits), idx, (width, idx))

    def test_find_first_one_existing_logic(self) -> None:
        # Audit the unchanged LSB-first algorithm; width=1 default remains excluded.
        for width in (2, 3, 4, 8, 9, 12):
            for bitmap in range(1 << width):
                location = 0
                for idx in reversed(range(width)):
                    if bitmap & (1 << idx):
                        location = idx
                onehot = bitmap & ~prefix_masks(bitmap, width)
                expected = bitmap & -bitmap
                self.assertEqual(onehot, expected)
                self.assertEqual(location, expected.bit_length() - 1 if expected else 0)

    def test_scheduler_all_requests_at_every_priority_position(self) -> None:
        for width in (1, 2, 3, 5, 8):
            for last in range(width):
                mask = ((1 << width) - 1) ^ ((1 << (last + 1)) - 1)
                for req in range(1 << width):
                    grant, _new_mask = scheduler_step(req, width, mask, True)
                    expected = 0
                    for offset in range(1, width + 1):
                        idx = (last + offset) % width
                        if req & (1 << idx):
                            expected = 1 << idx
                            break
                    self.assertEqual(grant, expected, (width, last, req))
                    self.assertEqual(scheduler_step(req, width, mask, False), (0, mask))

    def test_scheduler_random_sequences_reset_pause_and_fairness(self) -> None:
        rng = random.Random(20261021)
        for width in (1, 3, 5, 64):
            mask, last = 0, width - 1
            for _ in range(2000):
                req = rng.getrandbits(width)
                enable, reset_n = rng.randrange(3) != 0, rng.randrange(50) != 0
                grant, mask = scheduler_step(req, width, mask, enable, reset_n)
                expected = 0
                if not reset_n:
                    last = width - 1
                elif enable:
                    for offset in range(1, width + 1):
                        idx = (last + offset) % width
                        if req & (1 << idx):
                            expected, last = 1 << idx, idx
                            break
                self.assertEqual(grant, expected)
            mask = 0
            sequence = []
            for _ in range(width * 3):
                grant, mask = scheduler_step((1 << width) - 1, width, mask, True)
                sequence.append(grant.bit_length() - 1)
            self.assertEqual(sequence, list(range(width)) * 3)

    def exercise_handshake(self, src_period: int, dst_period: int, phase: int, reset_at: int | None) -> None:
        model = HandshakeModel()
        pending: deque[int] = deque()
        rng = random.Random(src_period * 100 + dst_period * 10 + phase)
        offered, received_count = 1, 0
        for time in range(60000):
            reset_n = reset_at is None or not (reset_at <= time < reset_at + 17)
            if not reset_n:
                pending.clear()
            before = model.state.copy()
            fire, received = model.tick(time % src_period == 0, time >= phase and (time - phase) % dst_period == 0, rng.randrange(4) != 0 and offered <= 150, offered, reset_n)
            if fire:
                pending.append(offered)
                offered += 1
            if received is not None:
                self.assertTrue(pending, (time, model.state))
                self.assertEqual(received, pending.popleft())
                received_count += 1
            if reset_n and not fire:
                self.assertEqual(model.state["data"], before["data"])
            if offered > 150 and not pending and not model.state["req"] and not model.state["ack1"] and not model.state["valid"]:
                self.assertGreater(received_count, 0)
                return
        self.fail("Handshake did not drain within the bounded test")

    def test_handshake_clock_ratios_phases_and_coincident_edges(self) -> None:
        for src, dst, phase in ((3, 11, 0), (13, 2, 1), (7, 7, 0), (7, 7, 3), (5, 9, 2)):
            self.exercise_handshake(src, dst, phase, None)

    def test_handshake_coordinated_reset_during_transfer(self) -> None:
        for reset_at in range(1, 35):
            self.exercise_handshake(5, 7, 1, reset_at)


@unittest.skipIf(pyslang is None, "pyslang unavailable; install in .rtl_tools/python or current Python environment")
class PriorityRtlCompileTests(unittest.TestCase):
    def test_actual_rtl_and_benches_elaborate(self) -> None:
        for top, parameters, sources in bench_cases():
            with self.subTest(top=top, parameters=parameters):
                check_elaboration(self, top, parameters, sources)


@unittest.skipUnless(IVERILOG and VVP, "Icarus Verilog/vvp unavailable; Python checks are models, not RTL simulation")
class PriorityRtlSimulationTests(unittest.TestCase):
    def test_self_checking_rtl_benches(self) -> None:
        with tempfile.TemporaryDirectory(prefix=".rtl_sim_", dir=ROOT) as directory:
            for top, parameters, sources in bench_cases():
                with self.subTest(top=top, parameters=parameters):
                    check_simulation(self, top, parameters, sources, Path(directory))


if __name__ == "__main__":
    unittest.main()
