import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills/ascendc-aprof-profiling/scripts"
sys.path.insert(0, str(SCRIPTS))
from fast_task_samples import complete_calls


def table(path, *, mode="valid"):
    rows = ["Op Name,OP Type,Task Duration(us),Stream ID"]
    for index in range(20):
        stream = str(index) if mode == "between_calls" else "7"
        rows.append(f"CannBenchCacheClean,CannBenchCacheClean,12,{stream}")
        rows.extend([f"same,Target,30,{stream}", f"same,Target,50,{stream}"])
    if mode == "missing_column":
        rows = [row.rsplit(",", 1)[0] for row in rows]
    elif mode == "empty_id":
        rows[2] = "same,Target,30,"
    elif mode == "within_call":
        rows[2] = "same,Target,30,8"
    elif mode == "extra_task":
        rows.append("extra,Target,1,7")
    path.write_text("\n".join(rows) + "\n")
    return path


def test_complete_calls_keep_repeated_kernel_names(tmp_path):
    result = complete_calls(table(tmp_path / "kernel_details.csv"), None, ["same", "same"])
    assert result["values_us"] == [80] * 20
    assert result["median_us"] == 80


@pytest.mark.parametrize("mode,message", [("missing_column", "Stream ID"), ("empty_id", "Stream ID"),
    ("between_calls", "multiple streams"), ("within_call", "multiple streams"), ("extra_task", "reordered kernel")])
def test_reject_incomplete_or_changed_streams(tmp_path, mode, message):
    with pytest.raises(ValueError, match=message):
        complete_calls(table(tmp_path / "kernel_details.csv", mode=mode), None, ["same", "same"])


def test_present_malformed_primary_does_not_use_fallback(tmp_path):
    primary = tmp_path / "kernel_details.csv"
    primary.write_text("bad,table\n")
    fallback = table(tmp_path / "op_summary.csv")
    with pytest.raises(ValueError, match="Task CSV columns"):
        complete_calls(primary, fallback, ["same", "same"])
