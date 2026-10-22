"""Only an unreferenced, byte-identical third output can be reclaimed."""
from pathlib import Path
import sys
import time

import pytest

RELEASE = Path(__file__).resolve().parents[2] / "skill-libs/graph-base/0.5.1"
sys.path.insert(0, str(RELEASE / "skills/ascendc-aprof-profiling/scripts"))
import device_task_window_timing as collector
from aprof_runtime.local_evidence import LocalEvidence


@pytest.mark.parametrize("case", ["duplicate", "role_output", "indexed", "different", "outside",
    "relative", "symlink", "parent_symlink", "directory", "missing", "repeated_flag", "equal_flag"])
def test_redundant_output_requires_unreferenced_exact_session_copy(tmp_path, case):
    directory = tmp_path / "session"; directory.mkdir()
    store = LocalEvidence(tmp_path / "records")
    baseline, candidate = directory / "baseline.bin", directory / "candidate.bin"
    baseline.write_bytes(b"verified output"); candidate.write_bytes(b"verified output")
    output_hashes = {str(p): store.register_artifact(p) for p in (baseline, candidate)}
    final = directory / "final.bin"; final.write_bytes(b"verified output")
    target = final
    if case == "role_output": target = baseline
    elif case == "indexed":
        # Register final first in a separate index: identical bytes must not
        # hide that it is the actual path backing an existing evidence ref.
        store = LocalEvidence(tmp_path / "indexed-records")
        store.register_artifact(final)
    elif case == "different": final.write_bytes(b"different output")
    elif case == "outside":
        target = tmp_path / "outside.bin"; target.write_bytes(b"verified output")
    elif case == "relative": target = Path("final.bin")
    elif case == "symlink": final.unlink(); final.symlink_to(baseline)
    elif case == "parent_symlink":
        (directory / "link").symlink_to(directory, target_is_directory=True)
        target = directory / "link/final.bin"
    elif case == "directory": final.unlink(); final.mkdir()
    elif case == "missing": final.unlink()
    application = ["native", "--output", str(target)]
    if case == "repeated_flag": application += ["--output", str(final)]
    if case == "equal_flag": application += ["--output=" + str(final)]
    removed = collector._remove_redundant_output(application, directory, output_hashes, store,
                                                deadline=time.monotonic() + 5)
    assert removed is (case == "duplicate")
    assert baseline.read_bytes() == candidate.read_bytes() == b"verified output"
    if case not in {"duplicate", "missing"}:
        assert final.exists() or final.is_symlink()
    for reference in store._paths:
        store.verify_artifact(reference)
