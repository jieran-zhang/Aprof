from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from trace_v2_campaign import Campaign, main, prepare_plan


def digest(n):
    return f"sha256:{n:064x}"


def register(campaign, n=1, parent=None, basis=()):
    return campaign.register_candidate("exp", candidate_id=f"c{n}", source_hash=digest(n),
        patch_hash=digest(100+n), source_parent=parent or {"source_hash": digest(0)},
        decision_basis=list(basis), original_source_hash=digest(0))


def measured(d):
    return {**d, "sample_ids": [f'{d["comparison_id"]}:sample:{i}' for i in range(len(d["case_ids"]) * 60)],
        "evidence_report_ref": digest(900), "child_binary_hash": digest(901), "control_binary_hash": digest(902),
        "input_hashes": {str(case): digest(1000 + case) for case in d["case_ids"]}, "pairs_per_case": 30,
        "quality": {"scope": "externally_attested_current_epoch", "baseline_current_correctness_cases": list(range(1, 21)), "baseline_current_correctness_passed": True,
            "aa": {phase: {"control_source_hash": d["control_source_hash"], "control_binary_hash": digest(902),
                "epoch": d["epoch"], "evidence_report_ref": digest(903), "cv": 0.01, "role_bias": 0.01, "drift": 0.01}
                for phase in ("before", "reverse", "after")}}}


def close(campaign, candidate, **overrides):
    comparisons = [measured(d) for d in candidate["comparisons"]]
    kwargs = dict(observation_id=f'o{candidate["candidate_id"]}', candidate_id=candidate["candidate_id"],
                  correct=True, runtime_ok=True, stable=True, diagnostics={"normal_skill_report": "external/report.json"},
                  comparisons=comparisons, build_count=1)
    kwargs.update(overrides)
    campaign.close_observation("exp", **kwargs)


def test_original_dedup_and_independent_parent_comparisons():
    campaign = Campaign(prepare_plan("example", [2, 3]))
    first = register(campaign)
    assert first["comparisons"][0]["roles"] == ["child_vs_parent", "child_vs_original"]
    close(campaign, first, diagnostics={"normal_skill_report": "r", "speedup": 1.001, "gate_3pct": False})
    second = register(campaign, 2, {"candidate_id": "c1", "source_hash": digest(1)}, ["oc1"])
    assert len(second["comparisons"]) == 2
    close(campaign, second)
    assert campaign.validate()
    assert campaign.dry_run()["tasks"]["exp"]["remaining_budget"]["timing_groups"] == 4
    assert not campaign.dry_run()["execution_permitted"]


def test_feedback_and_chronological_references():
    campaign = Campaign(prepare_plan("example"))
    with pytest.raises(ValueError, match="already be closed"):
        register(campaign, basis=["future"])
    first = register(campaign)
    with pytest.raises(ValueError, match="feedback"):
        register(campaign, 2)
    close(campaign, first)
    before = deepcopy(campaign.plan)
    with pytest.raises(ValueError, match="identity mismatch"):
        register(campaign, 2, {"source_hash": digest(99)})
    assert campaign.plan == before


def test_identity_and_sample_reuse_rejected_transactionally():
    campaign = Campaign(prepare_plan("example"))
    first = register(campaign)
    close(campaign, first)
    second = register(campaign, 2)
    result = measured(second["comparisons"][0])
    result["sample_ids"][0] = "c1:comparison:0:sample:0"
    before = deepcopy(campaign.plan)
    with pytest.raises(ValueError, match="reused"):
        close(campaign, second, comparisons=[result])
    result["sample_ids"][0] = "fresh"
    result["patch_hash"] = digest(999)
    with pytest.raises(ValueError, match="identity mismatch"):
        close(campaign, second, comparisons=[result])
    assert before == campaign.plan


@pytest.mark.parametrize("outcome", ["correct", "runtime_ok", "stable"])
def test_ineligible_parent(outcome):
    campaign = Campaign(prepare_plan("example"))
    first = register(campaign)
    close(campaign, first, **{outcome: False})
    with pytest.raises(ValueError, match="ineligible"):
        register(campaign, 2, {"candidate_id": "c1", "source_hash": digest(1)})


def test_budgets_and_frozen_roster():
    campaign = Campaign(prepare_plan("example"))
    first = register(campaign)
    with pytest.raises(ValueError, match="budget"):
        close(campaign, first, profile_groups=4)
    close(campaign, first, profile_groups=3, build_count=6)
    second = register(campaign, 2)
    with pytest.raises(ValueError, match="budget"):
        close(campaign, second)
    close(campaign, second, build_count=0)
    campaign.freeze("exp")
    with pytest.raises(ValueError, match="frozen"):
        register(campaign, 3)
    assert Campaign(json.loads(json.dumps(campaign.plan))).validate()


def test_six_sources_and_timing_groups():
    campaign = Campaign(prepare_plan("example"))
    for n in range(1, 7):
        close(campaign, register(campaign, n))
    with pytest.raises(ValueError, match="source budget"):
        register(campaign, 7)
    assert campaign.plan["tasks"]["exp"]["used"] == {"source": 6, "build": 6, "timing_groups": 6, "profile_groups": 0}


def test_recovery_only_prestart_once():
    campaign = Campaign(prepare_plan("example"))
    campaign.recover_prestart("exp", epoch=0, reason="infrastructure unavailable before experiment")
    with pytest.raises(ValueError, match="one infrastructure recovery"):
        campaign.recover_prestart("exp", epoch=0, reason="again")
    campaign = Campaign(prepare_plan("example"))
    close(campaign, register(campaign), stable=False)
    with pytest.raises(ValueError, match="stability retries forbidden"):
        campaign.recover_prestart("exp", epoch=0, reason="unstable")


def test_checkpoint_tampering_and_probe_validation():
    for probes in ([2, 3, 4], [2, 2], [1], [True], [21]):
        with pytest.raises(ValueError):
            prepare_plan("example", probes)
    campaign = Campaign(prepare_plan("example"))
    close(campaign, register(campaign))
    campaign.plan["tasks"]["exp"]["used"]["build"] = 0
    with pytest.raises(ValueError, match="event history"):
        Campaign(campaign.plan)


def test_cli_is_new_file_only_and_dry_run_is_read_only(tmp_path, capsys):
    output = tmp_path / "paused.json"
    assert main(["prepare", "--campaign-id", "new", "--output", str(output)]) == 0
    original = output.read_bytes()
    with pytest.raises(FileExistsError):
        main(["prepare", "--campaign-id", "overwrite", "--output", str(output)])
    assert main(["dry-run", "--manifest", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "paused"
    assert output.read_bytes() == original


def test_no_sample_reuse_across_workloads():
    campaign = Campaign(prepare_plan("example"))
    close(campaign, register(campaign))
    candidate = campaign.register_candidate("foreach_norm", candidate_id="norm1", source_hash=digest(20),
        patch_hash=digest(21), source_parent={"source_hash": digest(22)},
        decision_basis=[], original_source_hash=digest(22))
    result = measured(candidate["comparisons"][0])
    result["sample_ids"][0] = "c1:comparison:0:sample:0"
    with pytest.raises(ValueError, match="reused"):
        campaign.close_observation("foreach_norm", observation_id="norm-o1", candidate_id="norm1",
            correct=True, runtime_ok=True, stable=True, diagnostics={"report": "r"}, comparisons=[result])
    result["sample_ids"][0] = "norm-fresh"
    campaign.close_observation("foreach_norm", observation_id="norm-o1", candidate_id="norm1",
        correct=True, runtime_ok=True, stable=True, diagnostics={"report": "r"}, comparisons=[result])
    assert campaign.validate()


def test_parent_source_and_complete_comparators_are_checked():
    campaign = Campaign(prepare_plan("example"))
    close(campaign, register(campaign))
    with pytest.raises(ValueError, match="parent source mismatch"):
        register(campaign, 2, {"candidate_id": "c1", "source_hash": digest(99)})
    second = register(campaign, 2, {"candidate_id": "c1", "source_hash": digest(1)})
    only_parent = [measured(second["comparisons"][0])]
    with pytest.raises(ValueError, match="both comparator roles"):
        close(campaign, second, comparisons=only_parent)


@pytest.mark.parametrize("mutation", ["samples", "aa", "baseline", "input"])
def test_stable_claim_requires_protocol_bound_external_quality(mutation):
    campaign = Campaign(prepare_plan("example"))
    candidate = register(campaign)
    result = measured(candidate["comparisons"][0])
    if mutation == "samples":
        result["sample_ids"] = result["sample_ids"][:1]
    elif mutation == "aa":
        result["quality"]["aa"]["before"]["cv"] = 0.06
    elif mutation == "baseline":
        result["quality"]["baseline_current_correctness_passed"] = False
    else:
        result["input_hashes"].pop("1")
    with pytest.raises(ValueError):
        close(campaign, candidate, comparisons=[result])
    assert not campaign.plan["tasks"]["exp"]["observations"]


def test_timing_group_contains_two_comparators_and_bare_hashes_normalize():
    campaign = Campaign(prepare_plan("example"))
    first = campaign.register_candidate("exp", candidate_id="c1", source_hash="1" * 64,
        patch_hash="2" * 64, source_parent={"source_hash": "0" * 64}, decision_basis=[], original_source_hash="0" * 64)
    close(campaign, first)
    second = campaign.register_candidate("exp", candidate_id="c2", source_hash="3" * 64,
        patch_hash="4" * 64, source_parent={"candidate_id": "c1", "source_hash": "1" * 64},
        decision_basis=["oc1"], original_source_hash="0" * 64)
    close(campaign, second)
    assert campaign.plan["tasks"]["exp"]["used"]["timing_groups"] == 2
    assert campaign.plan["tasks"]["exp"]["comparison_groups_used"] == 3
    assert second["source_parent"]["source_hash"] == "sha256:" + "1" * 64
    assert campaign.validate()


def test_empty_roster_freeze_requires_explicit_blocked_reason():
    campaign = Campaign(prepare_plan("example"))
    with pytest.raises(ValueError, match="blocked reason"):
        campaign.freeze("exp")
    campaign.freeze("exp", reason="No experiment started; infrastructure unavailable")
    assert campaign.validate()
