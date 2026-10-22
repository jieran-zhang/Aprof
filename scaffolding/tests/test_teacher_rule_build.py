"""CPU source proofs and mocked configure/build; no provider, CANN, or NPU."""
import json
from pathlib import Path
import shutil

import pytest

import task_screen_bridge as screen
from eval_tool_broker import BUDGET_POLICY, CONFIG, REVIEW_OBLIGATIONS, REVIEW_SOURCE_POLICY, inventory, pointer, review_inventory, final_review
import qualify_eval_tools
from review_packet import build_review_packet
from test_review_final_submission import review_events

MODEL = {'name': 'CPU-review-fixture', 'reasoning_effort': 'ultra'}


def save(path, value):
    path.write_text(json.dumps(value))
    return pointer(path)


class Commands:
    """Count the actual requested compiler actions, never execute CANN commands."""
    def __init__(self, assembly, operator):
        self.assembly, self.operator = assembly, operator
        self.calls, self.checks, self.fail = [], 0, None

    def remaining(self):
        self.checks += 1
        if self.fail == 'deadline':
            raise TimeoutError('original deadline expired')
        return 10

    def run(self, stage, argv, cwd):
        self.calls.append(stage)
        if stage == 'build' and self.fail != stage:
            directory = self.assembly / 'build'
            directory.mkdir()
            (directory / self.operator).write_bytes(b'CPU-only mocked build output')
        return {'argv': argv, 'cwd': str(cwd), 'exit_status': 1 if stage == self.fail else 0, 'error': None}


@pytest.fixture
def trial(tmp_path, monkeypatch):
    def make(operator='exp'):
        root = tmp_path / operator
        root.mkdir()
        work = root / 'work'; work.mkdir()
        roles = {}
        for role in screen.ROLES:
            values = screen.rule.source_tree(screen.rule.ROUND / operator / role)
            roles[role] = work / role
            for name, content in values.items():
                path = roles[role] / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        expected = {role: inventory(path) for role, path in roles.items()}
        assembly = root / 'assembly'
        proof = screen.assemble(operator, roles, assembly, expected_roles=expected, expected_headers=screen.rule.HEADERS)
        save(work / 'candidate_plan.json', {'purpose': 'CPU-only fixed-rule exploration; no graph route'})
        reviewer = root / 'reviewer'; anonymous = reviewer / 'root/work'
        anonymous.mkdir(parents=True)
        for role, source in roles.items():
            for name in review_inventory(inventory(source)):
                destination = anonymous / role / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / name, destination)
        attachments = {}
        for key, leaf in (('contract_ref','contract.json'), ('checklist_ref','checklist.json'),
                          ('boundaries_ref','boundaries.json'), ('prompt_ref','prompt.txt')):
            document = ({'critical_obligations':{name:'CPU fixture only' for name in REVIEW_OBLIGATIONS}}
                        if key=='checklist_ref' else {'operator':operator,'cases':[{'case_id':1}]})
            attachments[key] = save(anonymous / leaf, document)
        (anonymous / 'diff.txt').write_text('CPU fixture; source byte inventories are verified independently')
        obligations = {name: {'status': 'pass', 'reason': 'CPU fixture only',
            'anchors': [{'path': f'candidate/op_kernel/{operator}_kernel.asc', 'line': 1}]} for name in REVIEW_OBLIGATIONS}
        packet = build_review_packet(anonymous, expected_inventory={k:v for k,v in inventory(anonymous).items() if k!='prompt.txt'})
        (anonymous/'prompt.txt').write_text(packet['prompt'])
        attachments['prompt_ref']=pointer(anonymous/'prompt.txt')
        def refresh(unknown=False):
            obligations['dynamic_tails']['status'] = 'unknown' if unknown else 'pass'
            decision = {'accepted': not unknown, 'obligations': obligations}
            events = review_events(obligations)
            broker = []
            for leaf, rows in (('events.jsonl', events), ('broker.jsonl', broker)):
                (reviewer / leaf).write_text(''.join(json.dumps(row) + '\n' for row in rows))
            worker = {'role':'reviewer','status':'completed','usage':{'totalTokens':7},
                'model':MODEL['name'],'reasoning_effort':MODEL['reasoning_effort'],
                'events_ref':pointer(reviewer/'events.jsonl'),'broker_ref':pointer(reviewer/'broker.jsonl'),
                'submission':decision,'qualification_ref':{},'config':CONFIG,'worker_builds':0,
                'review_submission':final_review(events)[1], 'budget_policy':BUDGET_POLICY}
            review = {'schema_version':1,'review_source_policy':REVIEW_SOURCE_POLICY,'baseline_inventory':inventory(roles['baseline']),
                'candidate_inventory':inventory(roles['candidate']), 'plan_sha256':pointer(work/'candidate_plan.json')['sha256'],
                'worker_receipt_ref':save(reviewer/'worker.json',worker),'decision':decision,
                'input_inventory':inventory(anonymous), 'review_packet_binding':packet['binding'], **attachments}
            save(work/'candidate_review.json',review)
        refresh()
        # Provider tool qualification is the only mocked review check; the full
        # blind-review verifier still reads actual source/input/events/submit files.
        monkeypatch.setattr(qualify_eval_tools, 'verify_qualification', lambda *a, **kw: {'CPU_fixture': True})
        local = screen.LocalEvidence(root / 'records')
        for role in screen.ROLES:
            local.register_artifact(proof['historical_source_binding']['roles'][role]['path'])
        anchor = {'schema_version':1,'purpose':'promotion','protocol':'rule_task_admission_v1',
            'task_protocol':screen.bridge.timing.PROTOCOL,'operator':operator,
            'source_hashes':{r:proof['historical_source_binding']['roles'][r]['sha256'] for r in screen.ROLES},
            'source_review_ref':local.register_artifact(assembly/'source-review.json')}
        return root, work, assembly, proof, local, anchor, Commands(assembly,operator), refresh
    return make


def build(value, **kwargs):
    _, work, assembly, _, local, anchor, commands, _ = value
    return screen.bridge.build_teacher_rule_once(assembly, work, commands,
        model=kwargs.pop('model', MODEL), local=local, anchor_ref=local.register_json(anchor), **kwargs)


@pytest.mark.parametrize('defect', ['performance', 'docs', 'omitted_semantic_file', 'stale_policy'])
def test_blind_review_rejects_noncanonical_source_view(trial, defect):
    root, work, _, _, _, _, _, _ = trial()
    view = root / 'reviewer/root/work'
    receipt_path = work / 'candidate_review.json'
    receipt = json.loads(receipt_path.read_text())
    if defect == 'stale_policy':
        receipt.pop('review_source_policy')
    elif defect == 'omitted_semantic_file':
        (view / 'candidate/op_kernel/exp_kernel.asc').unlink()
    else:
        path = view / 'candidate' / ('results.json' if defect == 'performance' else 'docs/PLAN.md')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('historical timing: 12 us')
    # Updating the self-declared inventory must not bypass the frozen source view.
    receipt['input_inventory'] = inventory(view)
    save(receipt_path, receipt)
    with pytest.raises(ValueError, match='source view|actual candidate'):
        screen.bridge.verify_blind_source_review(work, screen.bridge.RELEASE, model=MODEL)


@pytest.mark.parametrize('operator', ['exp', 'sigmoid'])
def test_teacher_build_requires_real_blind_review_and_compiles_once(trial, operator):
    value = trial(operator)
    _, work, assembly, proof, local, anchor, commands, _ = value
    receipt = build(value)
    assert commands.calls == ['configure', 'build'] and commands.checks >= 4
    attempt = json.loads((assembly/'build-attempt.json').read_text())
    assert set(attempt) == {'source_review_hash','independent_review','route'}
    assert attempt['independent_review'] == pointer(work/'candidate_review.json')
    assert attempt['route']['mode'] == 'exploration'
    assert json.loads(local.verify_artifact(attempt['route']['anchor_ref']).read_text()) == anchor
    assert screen.checked_build(assembly, receipt)[0] == proof
    with pytest.raises(FileExistsError):
        build(value)
    assert commands.calls == ['configure', 'build']
    # The validation entry still demands its original legal route receipt.
    with pytest.raises(KeyError, match='route_receipt_ref'):
        screen.bridge.build_once(assembly, work, commands, model=MODEL, baseline_qualification={})
    assert commands.calls == ['configure', 'build']


@pytest.mark.parametrize('field,value', [('purpose','diagnostic'), ('protocol','legacy'),
    ('task_protocol','shared_buffer_msprof_task_window_v3'), ('operator','gelu'),
    ('source_hashes',{}), ('source_review_ref','sha256:'+'0'*64)])
def test_teacher_rejects_wrong_anchor_before_attempt(trial, field, value):
    case = trial(); case[5][field] = value
    with pytest.raises(ValueError, match='anchor'):
        build(case)
    assert case[6].calls == [] and not (case[2]/'build-attempt.json').exists()


@pytest.mark.parametrize('defect', ['missing','passed_only','unknown','wrong_model'])
def test_teacher_rejects_missing_or_untrusted_review(trial, defect):
    case = trial(); path = case[1]/'candidate_review.json'
    if defect == 'missing': path.unlink()
    elif defect == 'passed_only': save(path, {'passed':True})
    elif defect == 'unknown': case[7](unknown=True)
    model = dict(MODEL, name='wrong') if defect == 'wrong_model' else MODEL
    with pytest.raises((ValueError, OSError)):
        build(case, model=model)
    assert case[6].calls == [] and not (case[2]/'build-attempt.json').exists()


def test_teacher_rejects_unindexed_anchor_and_wrong_workspace(trial):
    case = trial(); root, work, assembly, _, local, anchor, commands, _ = case
    with pytest.raises(Exception, match='not indexed'):
        screen.bridge.build_teacher_rule_once(assembly, work, commands, model=MODEL,
            local=local, anchor_ref='sha256:'+'0'*64)
    other = root/'other-work'; shutil.copytree(work,other)
    with pytest.raises(ValueError, match='workspace'):
        screen.bridge.build_teacher_rule_once(assembly, other, commands, model=MODEL,
            local=local, anchor_ref=local.register_json(anchor))
    assert commands.calls == [] and not (assembly/'build-attempt.json').exists()


def test_teacher_retains_failed_compile_and_does_not_retry(trial):
    case = trial(); case[6].fail = 'build'
    with pytest.raises(RuntimeError, match='no retry'):
        build(case)
    failed = json.loads((case[2]/'build-receipt.json').read_text())
    assert failed['status'] == 'failed' and failed['binary'] is None
    assert len(failed['commands']) == 2
    with pytest.raises(FileExistsError):
        build(case)
    assert case[6].calls == ['configure','build']


def test_teacher_preserves_original_deadline(trial):
    case = trial(); case[6].fail = 'deadline'
    with pytest.raises(TimeoutError): build(case)
    assert case[6].calls == [] and not (case[2]/'build-attempt.json').exists()


def test_checked_build_rejects_forged_exploration_route(trial):
    case = trial(); receipt = build(case)
    attempt_path = case[2]/'build-attempt.json'
    attempt = json.loads(attempt_path.read_text())
    attempt['route'] = {'mode':'exploration','anchor_ref':'sha256:'+'0'*64,'allowed':True}
    save(attempt_path,attempt)
    value = json.loads(receipt.read_text()); value['attempt_ref'] = pointer(attempt_path); save(receipt,value)
    with pytest.raises(ValueError, match='route must be'):
        screen.checked_build(case[2],receipt)
