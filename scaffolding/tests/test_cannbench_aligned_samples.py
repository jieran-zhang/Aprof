import csv
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "collection/scripts"))
from cannbench_aligned_samples import parse_complete_calls


def write_table(path, rows, *, fallback=False):
    names = ("Op Name", "OP Type", "Task Duration(us)") if fallback else (
        "Name", "Type", "Duration(us)")
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[*names, "Stream ID"])
        writer.writeheader()
        for kind, name, value, stream_id in rows:
            writer.writerow(dict(zip([*names, "Stream ID"], [name, kind, value, stream_id])))


def test_complete_call_median_preserves_repeated_kernel_launches(tmp_path):
    path = tmp_path / "kernel_details.csv"
    rows = []
    for first, second in ((1, 9), (9, 1), (1, 1)):
        rows += [("CannBenchCacheClean", "clean", 50, "7"),
                 ("Foreach", "foreach", first, "7"),
                 ("Foreach", "foreach", second, "7")]
    write_table(path, rows)
    result = parse_complete_calls(path, None, [("candidate", ["foreach", "foreach"])] * 3)
    assert [row["complete_call_us"] for row in result["samples"]] == [10, 10, 2]
    assert result["median_complete_call_us"]["candidate"] == 10
    assert result["eviction_count"] == 3


def test_op_summary_is_used_only_when_kernel_details_is_absent(tmp_path):
    fallback = tmp_path / "op_summary.csv"
    write_table(fallback, [("CannBenchCacheClean", "clean", 100, "1"),
                           ("Foreach", "foreach", 4, "1")], fallback=True)
    expected = [("baseline", ["foreach"])]
    assert parse_complete_calls(None, fallback, expected)["median_complete_call_us"] == {"baseline": 4}
    primary = tmp_path / "kernel_details.csv"
    primary.write_text("Name,Type,Duration(us)\n")
    with pytest.raises(ValueError, match="empty kernel table"):
        parse_complete_calls(primary, fallback, expected)


@pytest.mark.parametrize("fault", ["missing_marker", "missing_kernel", "extra_kernel",
                                    "nan", "second_stream"])
def test_incomplete_or_mixed_complete_call_fails_closed(tmp_path, fault):
    path = tmp_path / "kernel_details.csv"
    rows = [("CannBenchCacheClean", "clean", 50, "7"),
            ("Foreach", "foreach", 2, "7"), ("Foreach", "foreach", 3, "7")]
    if fault == "missing_marker":
        rows.pop(0)
    elif fault == "missing_kernel":
        rows.pop()
    elif fault == "extra_kernel":
        rows.append(("Foreach", "foreach", 1, "7"))
    elif fault == "nan":
        rows[1] = ("Foreach", "foreach", "NaN", "7")
    else:
        rows[2] = ("Foreach", "foreach", 3, "8")
    write_table(path, rows)
    with pytest.raises(ValueError):
        parse_complete_calls(path, None, [("candidate", ["foreach", "foreach"])])
