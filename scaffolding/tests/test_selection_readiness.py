"""Small public decision metadata only; all raw replayers are existing fixture stubs."""
import importlib.util,json,os,sys
from pathlib import Path
import pytest
HERE=Path(__file__).resolve().parents[2]
LIVE=Path(os.environ.get('APROF_TEST_REPO',HERE))
sys.path[:0]=[str(HERE/'scaffolding/collection/scripts'),str(LIVE/'scaffolding/collection/scripts'),str(LIVE/'src'),str(LIVE/'scaffolding/tests')]
spec=importlib.util.spec_from_file_location('level2_report',HERE/'scaffolding/collection/scripts/level2_report.py');report=importlib.util.module_from_spec(spec);sys.modules['level2_report']=report;spec.loader.exec_module(report)
from test_level2_report import closed_roster,save,ptr,tree,partial
from msprof_exploration_execute import event

@pytest.fixture(autouse=True)
def bind_shared_report_fixture_to_module_under_test(monkeypatch):
    # Full-suite collection may already have imported the shared fixture against
    # a different module instance before this file loads its explicit source.
    # Keep raw-evidence stubs on the same instance exercised by these HOLD tests;
    # selection_reconsiderations and the public event validation remain real.
    import test_level2_report as fixtures
    monkeypatch.setattr(fixtures, 'report', report)

def hold(task,selection):
    old=save(task/'finalization/selection.json',selection)
    proof=save(task/'finalization/reconsideration-01/numeric.json',{'operator':task.name,'original_selection':ptr(old),'original_source_hash':selection['source_hash'],'unopened_payloads':[{'path':'/must/not/read/output.bin','sha256':'sha256:'+'a'*64}]})
    note=save(task/'finalization/reconsideration-01/reconsideration.json',{'version':'level2_final_selection_reconsideration_v1','operator':task.name,'status':'selected_source_fails_additional_legal_workload','original_selection':ptr(old),'numeric_proof':ptr(proof),'required_resolution':'Explicit decision required'})
    row=event(task,'final_selection_reconsideration_required',{'reconsideration':ptr(note),'numeric_proof':ptr(proof),'selection_unchanged':ptr(old)})
    return row,note,proof,old

def selected(run):return report.analysis.load(run/'final-selection.json')['selections']['maximum']

def test_hold_blocks_previously_complete_baseline_without_changing_rounds_or_winner(tmp_path,monkeypatch):
    run,task,*_=closed_roster(tmp_path,monkeypatch)
    assert report.build_report(run)['status']=='complete'
    row,note,proof,old=hold(task,selected(run));before=tree(run)
    result=report.build_report(run);operator=result['operators'][0]
    assert result['status']==operator['status']=='blocked'
    assert operator['completed_rounds']==3 and operator['final_evaluation']=='complete'
    assert operator['final_selection']['candidate_id']=='baseline'
    assert operator['final_selection']['status']=='reconsideration_required'
    assert operator['final_selection']['declared_selection_status']=='selected_baseline'
    assert operator['final_selection']['acceptance_ready'] is False
    assert operator['final_selection']['current_safe'] is False
    assert operator['selection_readiness']['unresolved'][0]['event_binding']['event_hash']==row['hash']
    assert tree(run)==before
    paths={r['path'] for r in result['evidence_index']}
    assert {str(note),str(proof),str(old),str(task/'events.jsonl')}<=paths
    assert '/must/not/read/output.bin' not in paths

@pytest.mark.parametrize('change',['unrelated_event','apparent_resolution','different_winner'])
def test_hold_never_silently_resolves(change,tmp_path,monkeypatch):
    run,task,ledger,*_=closed_roster(tmp_path,monkeypatch)
    hold(task,selected(run))
    if change=='unrelated_event':event(task,'owner_note',{'status':'done'})
    elif change=='apparent_resolution':event(task,'final_selection_reconsideration_resolved',{'status':'accepted'})
    else:
        value=selected(run);value.update(candidate_id='maximum003',source_hash=ledger.state['tasks']['maximum']['candidates']['maximum003']['source_hash'])
        save(run/'final-selection.json',{'version':'level2_final_selection_v1','selections':{'maximum':value}})
    result=report.build_report(run)
    assert result['status']=='blocked' and result['operators'][0]['final_selection']['acceptance_ready'] is False

@pytest.mark.parametrize('mutation',['note','proof','old_selection','event_body','truncated_journal','path_escape','symlink'])
def test_hold_metadata_tamper_fails_closed(tmp_path,monkeypatch,mutation):
    run,task,*_=closed_roster(tmp_path,monkeypatch);row,note,proof,old=hold(task,selected(run))
    if mutation in ('note','proof','old_selection'):
        p={'note':note,'proof':proof,'old_selection':old}[mutation];p.write_bytes(p.read_bytes()+b' ')
    elif mutation=='event_body':
        p=task/'events.jsonl';p.write_bytes(p.read_bytes().replace(b'final_selection_reconsideration_required',b'final_selection_reconsideration_ignored'))
    elif mutation=='truncated_journal':
        p=task/'events.jsonl';p.write_bytes(p.read_bytes()[:-1])
    elif mutation=='symlink':
        moved=old.with_name('moved.json');old.rename(moved);old.symlink_to(moved)
    else:
        foreign=save(tmp_path/'foreign.json',json.loads(note.read_bytes()));value=row['value'];value['reconsideration']=ptr(foreign)
        (task/'events.jsonl').unlink();event(task,row['kind'],value)
    before=tree(run);result=report.build_report(run)
    assert result['status']=='blocked' and result['operators'][0]['status']=='blocked'
    assert tree(run)==before

def test_readiness_gate_also_applies_before_ledger_exists(tmp_path):
    run,task,manifest=partial(tmp_path)
    selection={'candidate_id':'baseline','source_hash':manifest['baseline']['sha256'],'reason':'original'}
    save(run/'final-selection.json',{'version':'level2_final_selection_v1','selections':{'maximum':selection}})
    hold(task,selection)
    assert report.build_report(run)['operators'][0]['final_selection']['status']=='reconsideration_required'

def test_legacy_valid_journal_without_hold_preserves_report(tmp_path,monkeypatch):
    run,task,*_=closed_roster(tmp_path,monkeypatch)
    before=report.build_report(run)
    event(task,'owner_note',{'read_only':True})
    assert report.build_report(run)==before


def test_dangling_journal_cannot_hide_public_hold(tmp_path,monkeypatch):
    run,task,*_=closed_roster(tmp_path,monkeypatch)
    (task/'events.jsonl').symlink_to(task/'missing-journal')
    assert report.build_report(run)['status']=='blocked'
