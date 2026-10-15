"""New Level2 experiments preserve old ledgers and charge real feedback rounds."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scaffolding/collection/scripts"))
import msprof_exploration_campaign as c
from test_msprof_exploration_campaign import h, register, start, finish, observe, ready


def declaration(split="train"):
    return {"baseline_source_hash": h(1), "source_split": split,
            "repeat_by_case": {str(i): 1 if i == 20 else 10 for i in range(1, 21)},
            "pilot_ref": h(2)}


@pytest.fixture
def fresh(tmp_path):
    return c.create_fresh(tmp_path / "ledger", campaign_id="level2", workloads={"maximum": declaration()})


def test_new_roster_and_original_test_lineage(tmp_path):
    ledger = c.create_fresh(tmp_path / "ledger", campaign_id="level2", workloads={
        "rms_norm": declaration("test"), "group_norm": declaration("validation")})
    assert ledger.config["predecessor"] is None
    assert ledger.config["tasks"]["rms_norm"]["source_split"] == "test"
    assert ledger.status()["tasks"]["rms_norm"]["split"] == "train"
    assert ledger.status()["tasks"]["group_norm"]["split"] == "validation"
    assert ledger.status()["graph_policy_eligible"] is False
    assert c.POLICY["repeat"] == 10
    assert ledger.verify()["valid"]


def test_frozen_repeat_counts_and_mutation_rejected(fresh):
    register(fresh, "maximum001", workload="maximum")
    ready(fresh, "maximum001", workload="maximum")
    plan = fresh.timing_plan("maximum", "maximum001", purpose="search", manifest_ref=h(3))
    assert plan["repeat_by_case"] == {"1": 10, "8": 10, "14": 10, "20": 1}
    assert c.expected_samples(plan) == 4 * 6 * 2 * 30 * 2
    assert c.expected_complete_calls(plan) == 31 * 6 * 2 * 30 * 2
    changed = deepcopy(plan)
    changed["repeat_by_case"]["20"] = 10
    with pytest.raises(ValueError, match="frozen"):
        start(fresh, "bad", "timing", changed, cid="maximum001", workload="maximum")
    start(fresh, "good", "timing", plan, cid="maximum001", workload="maximum")
    assert fresh.status()["tasks"]["maximum"]["used"]["timing_groups"] == 1


def test_failed_sources_count_but_empty_feedback_does_not(fresh):
    basis = []
    for index in range(3):
        cid = f"maximum{index}"
        register(fresh, cid, source=200 + index, basis=basis, workload="maximum")
        with pytest.raises(ValueError, match="executed stage"):
            observe(fresh, "empty", [], cid=cid, workload="maximum")
        start(fresh, cid, "build", cid=cid, workload="maximum")
        finish(fresh, cid, outcome="build_failed", workload="maximum")
        oid = "observation-" + cid
        observe(fresh, oid, [cid], cid=cid, workload="maximum")
        basis = [oid]
        if index < 2:
            with pytest.raises(ValueError, match="three actual"):
                fresh.freeze(event_id="early", workload="maximum", candidate_ids=[], final_plans={}, reason="failed")
    fresh.freeze(event_id="freeze", workload="maximum", candidate_ids=[], final_plans={}, reason="three failures; baseline retained")
    state = fresh.status()["tasks"]["maximum"]
    assert state["new_rounds_started"] == state["new_source_attempts"] == 3
    assert state["used"]["build"] == 3
    assert fresh.verify()["valid"]


@pytest.mark.parametrize("bad", [{}, {"1": 1}, {str(i): 2 for i in range(1, 21)},
                                  {str(i): True for i in range(1, 21)}])
def test_repeat_map_is_complete_and_closed(tmp_path, bad):
    task = declaration(); task["repeat_by_case"] = bad
    with pytest.raises(ValueError, match="repeat"):
        c.create_fresh(tmp_path / "bad", campaign_id="bad", workloads={"maximum": task})
    assert not (tmp_path / "bad").exists()


def test_manifest_tampering_and_resume_preserve_cost(fresh):
    register(fresh, "maximum001", workload="maximum")
    start(fresh, "build", "build", cid="maximum001", workload="maximum")
    finish(fresh, "build", "build_failed", workload="maximum")
    observe(fresh, "failure", ["build"], cid="maximum001", workload="maximum")
    fresh.checkpoint(event_id="checkpoint", checkpoint_id="checkpoint", reason="resource interruption",
                     next_action="round two", resources_released=True)
    fresh.resume(event_id="resume", checkpoint_id="checkpoint", reason="resume work")
    assert fresh.status()["tasks"]["maximum"]["used"]["source"] == 1
    path = fresh.directory / "config.json"
    config = json.loads(path.read_text()); config["tasks"]["maximum"]["repeat_by_case"]["20"] = 10
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="config hash"):
        c.Campaign(fresh.directory)
