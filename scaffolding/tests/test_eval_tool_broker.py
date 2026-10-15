"""CPU-only broker/protocol checks; none represents hardware qualification."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import time

import pytest

import eval_tool_broker as broker
import evaluate_skill_release as evaluation
import qualify_eval_tools as qualification


def workspace(tmp_path):
    work = tmp_path / "work"
    (work / "candidate/op_kernel").mkdir(parents=True)
    (work / "candidate/op_kernel/test.asc").write_text("int tile = 1;\n")
    (work / "candidate/scripts").mkdir()
    (work / "candidate/scripts/oracle.py").write_text("assert True\n")
    (work / "candidate/CMakeLists.txt").write_text("project(test)\n")
    (work / "library").mkdir()
    (work / "library/SKILL.md").write_text("Read-only skill\n")
    (work / "context.json").write_text("{}")
    return work


def test_file_broker_rejects_escape_code_tools_stale_hash_and_protected_writes(tmp_path):
    work = workspace(tmp_path)
    api = broker.Broker(work, tmp_path / "calls.jsonl")
    path = work / "candidate/op_kernel/test.asc"
    for name in ("../outside", "/etc/passwd", "candidate/../../outside"):
        with pytest.raises(ValueError):
            api.call("read_file", {"path": name, "start_line": 1, "line_count": 2})
    with pytest.raises(ValueError, match="inventory"):
        api.call("exec_command", {"cmd": "cmake --build ."})
    for name in ("library/SKILL.md", "candidate/scripts/oracle.py", "candidate/CMakeLists.txt"):
        with pytest.raises(ValueError, match="only existing"):
            api.call("replace_text", {"path": name, "expected_sha256": broker.sha(work / name), "old_text": "x", "new_text": "y"})
    (work / "candidate/link.asc").symlink_to(path)
    with pytest.raises(ValueError, match="symlink"):
        api.call("read_file", {"path": "candidate/link.asc", "start_line": 1, "line_count": 1})
    with pytest.raises(ValueError, match="stale"):
        api.call("replace_text", {"path": "candidate/op_kernel/test.asc", "expected_sha256": "wrong", "old_text": "1", "new_text": "2"})
    api.call("replace_text", {"path": "candidate/op_kernel/test.asc", "expected_sha256": broker.sha(path), "old_text": "1", "new_text": "2"})
    assert path.read_text() == "int tile = 2;\n"
    assert api.call("search_text", {"path": "candidate/op_kernel", "text": "$(cmake)"}) == {"matches": []}
    for start, count in [(0, 1), (1, 0), (1, 501)]:
        with pytest.raises(ValueError, match="bounds"):
            api.call("read_file", {"path": "candidate/op_kernel/test.asc", "start_line": start, "line_count": count})


def test_reviewer_is_read_only_blind_and_unknown_rejects(tmp_path):
    work = workspace(tmp_path)
    api = broker.Broker(work, tmp_path / "review.jsonl", review=True)
    with pytest.raises(ValueError, match="scope"):
        api.call("read_file", {"path": "library/SKILL.md", "start_line": 1, "line_count": 1})
    (work / "candidate/results.json").write_text('{"speedup": 9}')
    with pytest.raises(ValueError, match="reviewer source scope"):
        api.call("read_file", {"path": "candidate/results.json", "start_line": 1, "line_count": 1})
    for name in ("replace_text", "read_wiki", "graph_route"):
        with pytest.raises(ValueError, match="inventory"):
            api.call(name, {})
    obligations = {name: {"status": "pass", "reason": "Synthetic parser test only", "anchors": [{"path": "candidate/op_kernel/test.asc", "line": 1}]}
                   for name in broker.REVIEW_OBLIGATIONS}
    obligations["dynamic_tails"]["status"] = "unknown"
    api.validate_review(obligations)
    from test_review_final_submission import review_events
    assert broker.final_review(review_events(obligations))[0]["accepted"] is False
    with pytest.raises(ValueError, match="inventory"):
        api.call("submit_review", {"obligations": obligations})


@pytest.mark.parametrize("defect", ["model", "effort", "instructions", "execution_tool", "additional_tools", "schema", "unfinished"])
def test_tool_capture_checks_actual_provider_request_and_completion(defect):
    tools = [{"type": "function", "name": item["name"], "description": item["description"], "parameters": item["inputSchema"]}
             for item in broker.tool_specs()]
    requests = [{"model": "frozen-model", "reasoning": {"effort": "ultra"}, "instructions": broker.BASE_INSTRUCTIONS, "tools": tools} for _ in range(2)]
    events = [{"method": "item/tool/call", "params": {"tool": "list_files", "arguments": {"path": "."}}},
              {"method": "turn/completed", "params": {"turn": {"status": "completed"}}}]
    args = dict(model="frozen-model", effort="ultra", review=False, wiki=False)
    qualification.verify_capture(requests, events, **args)
    if defect == "model":
        requests[1]["model"] = "fallback-model"
    elif defect == "effort":
        requests[1]["reasoning"]["effort"] = "medium"
    elif defect == "instructions":
        requests[1]["instructions"] = "unfrozen inherited instructions"
    elif defect == "execution_tool":
        requests[1]["tools"].append({"type": "function", "name": "exec_command"})
    elif defect == "additional_tools":
        requests[1]["input"] = [{"type": "additional_tools", "tools": [{"type": "custom", "name": "exec"}]}]
    elif defect == "schema":
        requests[1]["tools"][0]["parameters"] = {"type": "object"}
    else:
        events[-1]["params"]["turn"]["status"] = "failed"
    with pytest.raises(ValueError):
        qualification.verify_capture(requests, events, **args)


def test_catalog_overrides_only_tool_interface_and_preserves_model_and_efforts():
    original = {"models": [{"slug": "gpt-6-sol", "tool_mode": "code_mode_only", "multi_agent_version": "v2", "use_responses_lite": True,
                            "supported_reasoning_levels": [{"effort": "max"}, {"effort": "ultra"}],
                            "experimental_supported_tools": ["clock"], "node_repl_disabled": False}]}
    frozen = qualification.restricted_catalog(original)
    assert original["models"][0]["tool_mode"] == "code_mode_only"
    assert frozen["models"][0]["slug"] == "gpt-6-sol"
    assert frozen["models"][0]["supported_reasoning_levels"] == original["models"][0]["supported_reasoning_levels"]
    assert "tool_mode" not in frozen["models"][0]
    assert "multi_agent_version" not in frozen["models"][0]
    assert frozen["models"][0]["use_responses_lite"] is False


def test_review_replay_rejects_non_source_and_invalid_line_anchors(tmp_path):
    work = workspace(tmp_path)
    api = broker.Broker(work, tmp_path / "review.jsonl", review=True)
    obligations = {name: {"status": "pass", "reason": "Synthetic parser test only", "anchors": [{"path": "candidate/op_kernel/test.asc", "line": 1}]}
                   for name in broker.REVIEW_OBLIGATIONS}
    api.validate_review(obligations)
    obligations["dynamic_tails"]["anchors"][0]["line"] = 100
    with pytest.raises(ValueError, match="outside"):
        api.validate_review(obligations)
    obligations["dynamic_tails"]["anchors"] = [{"path": "contract.json", "line": 1}]
    with pytest.raises(ValueError, match="implementation sources"):
        api.validate_review(obligations)


def test_wiki_only_available_in_explicit_arm(tmp_path):
    work = workspace(tmp_path)
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "index.json").write_text(json.dumps({"entries": {"case": {"page": "case.md"}}}))
    (wiki / "case.md").write_text("Frozen conditional observation.")
    with pytest.raises(ValueError, match="inventory"):
        broker.Broker(work, tmp_path / "off.jsonl").call("read_wiki", {"page_id": "case"})
    result = broker.Broker(work, tmp_path / "on.jsonl", wiki=wiki).call("read_wiki", {"page_id": "case"})
    assert result["sha256"] == broker.sha(wiki / "case.md")
    assert result["bytes"] == len(result["text"].encode())


def test_graph_route_replays_frozen_context_and_masks_unknown(tmp_path):
    # Fresh process selects the candidate runtime. Synthetic profile facts are
    # deliberately confined to a CPU routing test, never a gate receipt.
    root = Path(__file__).resolve().parents[2]
    program = r'''
import json, sys
from pathlib import Path
root, out = map(Path, sys.argv[1:])
release = root / 'skill-libs/graph-base/1.0.0'
sys.path[:0] = [str(release / 'runtime/src'), str(root / 'scaffolding/tests'), str(root / 'scaffolding/collection/scripts')]
from test_planning import context_example
from eval_tool_broker import BUDGET_POLICY, CONFIG, REVIEW_OBLIGATIONS, REVIEW_SOURCE_POLICY, inventory, pointer, final_review
from review_packet import build_review_packet
from test_review_final_submission import review_events
from eval_candidate_evidence import replay_route, verify_candidate_evidence, verify_blind_source_review
value = context_example()
value['evidence']['predicate_states'] = {'predicate.profile.overlap_low': 'unknown'}
(out / 'context.json').write_text(json.dumps(value))
(out / 'qualification.json').write_text(json.dumps({'status': 'passed', 'synthetic': 'CPU-only route test'}))
registry = {'schema_version':1,'graph':pointer(release / 'skillgraph/versions/v0002/graph.json'),
 'contexts': {'baseline': {'context':pointer(out / 'context.json'), 'baseline_qualification':pointer(out / 'qualification.json'),
 'evidence':[pointer(out / 'context.json')]}}}
(out / 'registry.json').write_text(json.dumps(registry))
ref = pointer(out / 'registry.json')
result = replay_route(ref,'baseline',release)
assert result['route']['selected_edge_id'] == 'edge.prior.unknown.noop'
assert not next(x for x in result['route']['candidates'] if x['edge_id']=='edge.prior.pipeline.software_pipeline')['allowed']
# Exercise source-review replay with synthetic protocol records only. This is
# not a hardware qualification or real model review.
work = out / 'work'
reviewer = out / 'reviewer'
review_work = reviewer / 'root/work'
for folder in (work / 'baseline',work / 'candidate',review_work / 'baseline',review_work / 'candidate'):
 (folder / 'op_kernel').mkdir(parents=True)
 (folder / 'op_kernel/kernel.asc').write_text('int tile = 1;\n')
 for name in ('CMakeLists.txt','op_host/fixture.asc','op_kernel/fixture_kernel.asc',
              'op_host/aprof_device_timer.h','op_host/data_utils.h','scripts/verify_result.py','scripts/gen_data.py','scripts/cases.py'):
  target=folder/name; target.parent.mkdir(parents=True,exist_ok=True);target.write_text('// CPU fixture source\n')
def write(path, value):
 path.write_text(json.dumps(value))
 return pointer(path)
route_ref = write(work / 'route_receipt.json',result)
plan = {'route_receipt_ref':route_ref,'transformation_id':'transformation.noop',
 'parameters': {'no_mutation':True,'reason':'CPU parser fixture only'}}
write(work / 'candidate_plan.json',plan)
obligations = {name:{'status':'pass','reason':'CPU parser fixture only','anchors':[{'path':'candidate/op_kernel/kernel.asc','line':1}]} for name in REVIEW_OBLIGATIONS}
decision = {'accepted':True,'obligations':obligations}
events = review_events(obligations)
(reviewer / 'events.jsonl').write_text(''.join(json.dumps(item)+'\n' for item in events))
(reviewer / 'broker.jsonl').write_text('')
worker = {'role':'reviewer','status':'completed','usage':{'totalTokens':7},'model':'synthetic-model','reasoning_effort':'ultra',
 'events_ref':pointer(reviewer/'events.jsonl'),'broker_ref':pointer(reviewer/'broker.jsonl'),'submission':decision,
 'qualification_ref':{},'config':CONFIG,'worker_builds':0,'budget_policy':BUDGET_POLICY,'review_submission':final_review(events)[1]}
worker_ref = write(reviewer / 'worker.json',worker)
attachments = {}
for key, name in [('contract_ref','contract.json'),('checklist_ref','checklist.json'),('boundaries_ref','boundaries.json'),('prompt_ref','prompt.txt')]:
 document=({'critical_obligations':{name:'CPU fixture only' for name in REVIEW_OBLIGATIONS}}
           if key=='checklist_ref' else {'operator':'fixture','cases':[{'case_id':1}]})
 (review_work/name).write_text(json.dumps(document))
 attachments[key] = pointer(review_work/name)
(review_work/'diff.txt').write_text('')
packet = build_review_packet(review_work,expected_inventory={k:v for k,v in inventory(review_work).items() if k!='prompt.txt'})
(review_work/'prompt.txt').write_text(packet['prompt']);attachments['prompt_ref']=pointer(review_work/'prompt.txt')
review = {'schema_version':1,'review_source_policy':REVIEW_SOURCE_POLICY,'baseline_inventory':inventory(work/'baseline'),'candidate_inventory':inventory(work/'candidate'),
 'plan_sha256':pointer(work/'candidate_plan.json')['sha256'],'worker_receipt_ref':worker_ref,'decision':decision,
 'input_inventory':inventory(review_work),'review_packet_binding':packet['binding'],**attachments}
write(work / 'candidate_review.json',review)
import qualify_eval_tools
qualify_eval_tools.verify_qualification = lambda *a,**k:{'synthetic_cpu_test':True}
verified = verify_candidate_evidence(work,release)
assert verified['accepted'] is True
assert set(verified) == {'accepted','source_review','route_receipt','source_review_ref','route_receipt_ref'}
model = {'name':'synthetic-model','reasoning_effort':'ultra'}
blind = verify_blind_source_review(work,release,model=model)
assert set(blind) == {'accepted','source_review','source_review_ref'}
assert blind == {key:verified[key] for key in blind}
# Independent review can replay without a route, but cannot make the ordinary
# candidate verifier accept a missing or unqualified route.
route_bytes = (work/'route_receipt.json').read_bytes()
(work/'route_receipt.json').unlink()
assert verify_blind_source_review(work,release,model=model)['accepted'] is True
try: verify_candidate_evidence(work,release,model=model)
except (ValueError,OSError): pass
else: raise AssertionError('blind review bypassed required graph route')
(work/'route_receipt.json').write_bytes(route_bytes)
for wrong in ({'name':'other','reasoning_effort':'ultra'}, {'name':'synthetic-model','reasoning_effort':'low'}):
 try: verify_blind_source_review(work,release,model=wrong)
 except ValueError as error: assert 'frozen evaluation model' in str(error)
 else: raise AssertionError('different reviewer model/effort admitted')
qualification_checker = qualify_eval_tools.verify_qualification
def reject_qualification(*a,**k): raise ValueError('unqualified review tool interface')
qualify_eval_tools.verify_qualification = reject_qualification
try: verify_blind_source_review(work,release,model=model)
except ValueError as error: assert 'unqualified review tool interface' in str(error)
else: raise AssertionError('independent review skipped tool qualification')
qualify_eval_tools.verify_qualification = qualification_checker
plan_bytes = (work/'candidate_plan.json').read_bytes()
(work/'candidate_plan.json').write_text('{}')
try: verify_blind_source_review(work,release,model=model)
except ValueError as error: assert 'actual candidate' in str(error)
else: raise AssertionError('review from another plan admitted')
(work/'candidate_plan.json').write_bytes(plan_bytes)
try: verify_candidate_evidence(work,release,baseline_qualification={'path':'different'})
except ValueError as error: assert 'different qualified baseline' in str(error)
else: raise AssertionError('route context from another baseline admitted')
worker['usage'] = {'totalTokens':8001}
write(reviewer/'worker.json',worker)
try: verify_candidate_evidence(work,release)
except ValueError as error: assert 'hash changed' in str(error)
else: raise AssertionError('stale review receipt admitted')
worker['events_ref'] = pointer(reviewer/'events.jsonl')
review['worker_receipt_ref'] = write(reviewer/'worker.json',worker)
write(work/'candidate_review.json',review)
try: verify_candidate_evidence(work,release)
except ValueError as error: assert 'model usage receipt' in str(error)
else: raise AssertionError('unbound worker usage admitted')
events = review_events(obligations,total=80001)
(reviewer/'events.jsonl').write_text(''.join(json.dumps(item)+'\n' for item in events))
worker['usage'],worker['events_ref'] = {'totalTokens':80001},pointer(reviewer/'events.jsonl')
worker['review_submission']=final_review(events)[1]
review['worker_receipt_ref'] = write(reviewer/'worker.json',worker)
write(work/'candidate_review.json',review)
assert verify_blind_source_review(work,release)['accepted'] is True
(work/'candidate/op_kernel/kernel.asc').write_text('int tile = 2;\n')
try: verify_candidate_evidence(work,release)
except ValueError as error: assert 'actual candidate' in str(error)
else: raise AssertionError('unreviewed source edit admitted')
review['candidate_inventory'] = inventory(work/'candidate')
(review_work/'candidate/op_kernel/kernel.asc').write_text('int tile = 2;\n')
packet=build_review_packet(review_work,expected_inventory={k:v for k,v in inventory(review_work).items() if k!='prompt.txt'})
(review_work/'prompt.txt').write_text(packet['prompt'])
review.update(input_inventory=inventory(review_work),review_packet_binding=packet['binding'],prompt_ref=pointer(review_work/'prompt.txt'))
write(work/'candidate_review.json',review)
assert verify_blind_source_review(work,release,model=model)['accepted'] is True
try: verify_candidate_evidence(work,release)
except ValueError as error: assert 'NOOP route' in str(error)
else: raise AssertionError('NOOP route authorized a mutation')
(work/'candidate/op_kernel/kernel.asc').write_text('int tile = 1;\n')
(review_work/'candidate/op_kernel/kernel.asc').write_text('int tile = 1;\n')
review['input_inventory'] = inventory(review_work)
review['candidate_inventory'] = inventory(work/'candidate')
write(work/'candidate_review.json',review)
(review_work/'wiki.md').write_text('unexpected reviewer context')
try: verify_candidate_evidence(work,release)
except ValueError as error: assert 'unrecorded material' in str(error)
else: raise AssertionError('unrecorded reviewer context admitted')
try: replay_route(ref,'invented',release)
except ValueError: pass
else: raise AssertionError('unknown context admitted')
(out / 'context.json').write_text('{}')
try: replay_route(ref,'baseline',release)
except ValueError: pass
else: raise AssertionError('changed evidence admitted')
'''
    subprocess.run([sys.executable, "-c", program, str(root), str(tmp_path)], check=True, capture_output=True, text=True)


def test_blind_review_materialization_preserves_shared_budget(tmp_path, monkeypatch):
    trial = tmp_path / "trial"
    original = trial / "worker/root/work"
    for role in ("baseline", "candidate"):
        (original / role / "op_kernel").mkdir(parents=True)
        (original / role / "op_kernel/kernel.asc").write_text("int tile = " + ("1" if role == "baseline" else "2") + ";\n")
        (original / role / "docs").mkdir()
        (original / role / "docs/performance.md").write_text("historical latency = " + role)
        (original / role / "results.json").write_text('{"all_passed": true}')
        (original / role / "harness.patch").write_text("historical performance patch")
        (original / role / "op_kernel/metadata.json").write_text('{"latency": 12}')
        (original / role / "scripts").mkdir()
        (original / role / "scripts/oracle.py").write_text("# exact oracle source\n")
    (original / "candidate_plan.json").write_text('{"secret_arm":"must not enter reviewer"}')
    (original / "wiki").mkdir()
    (original / "wiki/private.md").write_text("must not enter reviewer")
    task = {}
    for key in ("review_contract", "review_checklist", "review_boundaries"):
        path = tmp_path / (key + ".json")
        path.write_text("{}")
        task[key] = broker.pointer(path)
    manifest = {"tasks": {"gelu": task}, "model": {"name": "frozen-model", "reasoning_effort": "ultra"}, "worker_qualification": {}}

    async def worker(work, output, model, effort, tokens, seconds, **kwargs):
        assert tokens is None and 0 < seconds <= 3600
        assert model == "frozen-model" and effort == "ultra" and kwargs["review"]
        assert not (work / "candidate_plan.json").exists() and not (work / "wiki").exists()
        assert {path.name for path in work.iterdir()} == {"baseline", "candidate", "contract.json", "checklist.json", "boundaries.json", "diff.txt", "prompt.txt"}
        for role in ("baseline", "candidate"):
            assert broker.inventory(work / role) == broker.review_inventory(broker.inventory(original / role))
            assert set(broker.inventory(work / role)) == {"op_kernel/kernel.asc", "scripts/oracle.py"}
        assert "historical latency" not in (work / "diff.txt").read_text()
        assert "int tile = 2" in (work / "diff.txt").read_text()
        result = {"status": "completed", "usage": {"totalTokens": 42}, "submission": {"accepted": False, "obligations": {}}}
        evaluation.dump(output / "worker.json", result)
        return result

    import review_packet
    monkeypatch.setattr(review_packet, "build_review_packet", lambda work, **kw: {"prompt":"CPU packet wiring fixture", "binding":{"CPU":"fixture only"}})
    monkeypatch.setattr(evaluation, "run_worker", worker)
    result = {"status": "completed"}
    evaluation.review_candidate(manifest, {"operator": "gelu"}, trial, time.monotonic(), result)
    assert result["status"] == "source_review_rejected"
    assert result["reviewer_started"]
    assert (original / "candidate_review.json").exists()
    receipt = json.loads((original / "candidate_review.json").read_text())
    assert receipt["review_source_policy"] == broker.REVIEW_SOURCE_POLICY
    assert "results.json" in receipt["baseline_inventory"]
