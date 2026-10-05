from __future__ import annotations

import csv
import importlib.util
import json
import statistics
from pathlib import Path

import pytest

from aprof_runtime.exploration import _profile_metric
from aprof_runtime.errors import ContractError
from aprof_runtime.store import EpisodeStore
from aprof_runtime.traces import register_json_artifact

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("normalizer", ROOT / "scripts/normalize_aprof_profile.py")
normalizer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(normalizer)
compressor = normalizer._COMPRESSOR


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader(); writer.writerows(rows)


def raw_case(root, kernel="exp_kernel", offset=0):
    for invocation in range(5):
        directory = root / "OPPROF_20260907_test" / kernel / str(invocation)
        stamp = f"20260907154719{invocation:03}"
        write_csv(directory / f"OpBasicInfo_{stamp}.csv", ["Op Name", "Task Duration(us)", "Block Dim"],
            [{"Op Name": kernel, "Task Duration(us)": 10 + invocation + offset, "Block Dim": 2}])
        write_csv(directory / f"PipeUtilization_{stamp}.csv", ["block_id", "sub_block_id", "aiv_time(us)", "aiv_vec_ratio", "aic_time(us)"],
            [{"block_id": core, "sub_block_id": "vector0", "aiv_time(us)": 10 + invocation + core + offset,
              "aiv_vec_ratio": .2 + core * .1 + offset, "aic_time(us)": "NA"} for core in range(2)])


def test_known_timestamped_tables_only():
    for name in ("PipeUtilization", "Memory", "OpBasicInfo", "L2Cache"):
        assert compressor._csv_kind(Path(f"{name}_20260907154719738.csv")) == name.lower()
    assert compressor._csv_kind(Path("PipeUtilization_untrusted.csv")) is None
    assert compressor._csv_kind(Path("UnknownTable_20260907154719738.csv")) is None
    assert compressor._csv_kind(Path("Memory_123.csv")) is None


def test_timestamped_compressor_preserves_repeats_and_kernel_scope(tmp_path):
    raw_case(tmp_path, "exp_kernel")
    raw_case(tmp_path, "other_kernel", 100)
    args = compressor.build_parser().parse_args(["--input", str(tmp_path), "--output", str(tmp_path / "symptoms.json"),
        "--op-name", "exp_kernel", "--available-cores", "2"])
    result = compressor.compress(args)
    assert result["features"]["task_duration_samples_us"] == [10, 11, 12, 13, 14]
    assert result["features"]["pipe_ratios"]["aiv_vec"] == pytest.approx(.25)
    assert result["features"]["per_core_time"] == [12, 13]
    assert result["features"]["per_core_imbalance"] == pytest.approx(1 / 13)


def test_normalizer_preserves_sources_units_invocations_and_runtime_replay(tmp_path):
    raw = tmp_path / "raw"; raw_case(raw)
    with EpisodeStore(tmp_path / "episodes.sqlite") as store:
        result = normalizer.normalize_profile(raw, tmp_path / "normalized", 1, store)
        profile = result["profiles"][0]
        assert profile["kernel"] == "exp_kernel"
        assert profile["invocation_count"] == 5
        _, ratio = _profile_metric(store, profile["content_hash"], "PipeUtilization/aiv_vec_ratio")
        assert ratio["unit"] == "ratio"
        assert ratio["value"] == pytest.approx(.25)
        assert len(ratio["samples"]) == 10
        _, duration = _profile_metric(store, profile["content_hash"], "OpBasicInfo/Task Duration(us)")
        assert duration["unit"] == "us"
        assert duration["samples"] == [10, 11, 12, 13, 14]
        manifest = json.loads(Path(result["manifest_path"]).read_text())
        assert len(manifest["raw_artifacts"]) == 10
        assert manifest["production_timing_eligible"] is False
        for artifact in manifest["raw_artifacts"]:
            store.verify_artifact(artifact["content_hash"])
        combined = next(item for item in manifest["combined_tables"] if item["table"] == "PipeUtilization")
        rows = list(csv.DictReader(store.verify_artifact(combined["content_hash"]).open()))
        assert [row["block_id"] for row in rows] == ["0", "1"] * 5
        assert all(row["aprof_source_hash"].startswith("sha256:") for row in rows)
        assert all(row["aic_time(us)"] == "NA" for row in rows)
        normalized = json.loads(Path(profile["path"]).read_text())
        assert "PipeUtilization/aic_time(us)" not in normalized["metrics"]
        assert normalizer.normalize_profile(raw, tmp_path / "normalized", 1, store) == result


def test_normalizer_keeps_kernels_separate_and_rejects_overwrite(tmp_path):
    raw = tmp_path / "raw"; raw_case(raw); raw_case(raw, "other", 100)
    with EpisodeStore(tmp_path / "episodes.sqlite") as store:
        result = normalizer.normalize_profile(raw, tmp_path / "normalized", 1, store, kernel="exp_kernel")
        assert [item["kernel"] for item in result["profiles"]] == ["exp_kernel"]
        with pytest.raises(FileExistsError):
            normalizer.normalize_profile(raw, tmp_path / "normalized", 2, store, kernel="exp_kernel")
        with pytest.raises(ValueError, match="outside"):
            normalizer.normalize_profile(raw, raw / "nested", 1, store)


def test_nonfinite_values_are_not_filled_or_claimed(tmp_path):
    raw = tmp_path / "raw"; raw_case(raw)
    sample = next(raw.rglob("PipeUtilization*.csv"))
    sample.write_text(sample.read_text().replace("0.2", "NaN"))
    with EpisodeStore(tmp_path / "episodes.sqlite") as store:
        result = normalizer.normalize_profile(raw, tmp_path / "normalized", 1, store)
        profile = json.loads(Path(result["profiles"][0]["path"]).read_text())
        assert "PipeUtilization/aiv_vec_ratio" not in profile["metrics"]
        manifest = json.loads(Path(result["manifest_path"]).read_text())
        note = next(item for item in manifest["metric_notes"] if item["field"] == "aiv_vec_ratio")
        assert note["invalid_count"] == 1


def test_combined_csv_cannot_replace_original_measurement_values(tmp_path):
    raw = tmp_path / "raw"; raw_case(raw)
    with EpisodeStore(tmp_path / "episodes.sqlite") as store:
        result = normalizer.normalize_profile(raw, tmp_path / "normalized", 1, store)
        profile = json.loads(Path(result["profiles"][0]["path"]).read_text())
        metric = profile["metrics"]["PipeUtilization/aiv_vec_ratio"]
        with store.verify_artifact(metric["source_artifact_hash"]).open() as source:
            reader = csv.DictReader(source)
            fields, rows = reader.fieldnames, list(reader)
        rows[0]["aiv_vec_ratio"] = "9.0"
        modified = tmp_path / "modified.csv"
        write_csv(modified, fields, rows)
        metric["source_artifact_hash"] = store.register_artifact(modified)
        metric["samples"][0] = 9.0
        metric["value"] = statistics.median(metric["samples"])
        digest = register_json_artifact(store, profile)
        with pytest.raises(ContractError, match="differs from its bound original"):
            _profile_metric(store, digest, "PipeUtilization/aiv_vec_ratio")
