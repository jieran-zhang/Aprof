"""Scoped publication joins; synthetic leaves never claim hardware qualification."""
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import sys

import pytest

import release_skill_lib as release
import verify_exp_scoped_publication as scoped
import verify_teacher_wiki as teacher
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.jsonio import file_hash


def pointer(path):
    return {'path': str(path), 'sha256': file_hash(path)}


@pytest.fixture
def packet(tmp_path, monkeypatch):
    repo = tmp_path/'workspace/repo'; root = repo/'skill-libs/graph-base/1.0.0'
    root.mkdir(parents=True)
    monkeypatch.setattr(scoped, 'REPO', repo)
    monkeypatch.setattr(teacher, 'verify_frozen_machine_rules', lambda *args: None)
    monkeypatch.setattr(teacher, 'verify_promotion_runtime', lambda *args, **kwargs: None)
    directory = repo.parent/'handoff'; directory.mkdir()
    local = LocalEvidence(directory/'records')
    put = local.register_json
    amendment = directory/'amendment.json'
    amendment.write_text(json.dumps(dict(scoped.SCOPE, created_at=123)))
    audit = repo/'scaffolding/curation/graph-base-1.0.0.json'
    audit.parent.mkdir(parents=True); audit.write_text('{}')
    promotion = dict(kind='teacher_exp_continuation_promotion', proposal_id='exp-one',
        wiki_id='exp-tile8192', target_skill='skills/ascendc-aprof-optimization/SKILL.md',
        amendment_ref=file_hash(amendment), campaign_ref=put({'original': 'failed campaign'}))
    promotion_ref = put(promotion)
    event = {key:promotion[key] for key in ('proposal_id','wiki_id','target_skill')}
    event.update(decision='accepted', validation_receipt=teacher.source(local.verify_artifact(promotion_ref), repo.parent))
    db = directory/'retained.sqlite'
    conn = sqlite3.connect(db); conn.execute('CREATE TABLE artifacts(content_hash TEXT PRIMARY KEY)'); conn.commit();conn.close()
    report = dict(schema_version=1,kind='exp_scoped_publication_v1',release_id='graph-base/1.0.0',
        amendment=pointer(amendment), campaign_ref=promotion['campaign_ref'], promotion_ref=promotion_ref,
        trusted_before_inventory_ref=put({'skill':'before'}), archives=[pointer(db)], local_indices=[],
        trials={'exp':dict(index_ref=put({'old':'index'}),dispatcher_result_ref=put({'old':'failed'}),
                           source_archive_ref=put({'old':'source archive'})),
                'sigmoid':dict(index_ref=put({'sigmoid':'index'}),not_run_ref=put({'sigmoid':'not_run'}))},
        trusted_review_refs=dict(archive_inventory_ref=put({'old':'inventory'}),producer_snapshot_ref=put({'old':'producers'})),
        teacher_audit=pointer(audit))
    index = local.write_index(directory/'index.json'); report['local_indices']=[pointer(index)]
    report_path = directory/'publication.json'
    calls=[]
    outcome=dict(valid=True,operator='exp',eligible_for_teacher_edit=True,
        edit=dict(applied=True,target_skill=promotion['target_skill'],before='before',after='after'),
        sources={'wiki_id':'exp-tile8192'},machine={'verdict':'production_safe_gain'})
    def verifier(reader,reference,**kwargs):
        calls.append((reader,reference,kwargs)); reader.verify_artifact(reference)
        return copy.deepcopy(outcome)
    monkeypatch.setitem(sys.modules,'task_rule_gate_completion_admission',SimpleNamespace(verify_continuation_promotion=verifier))
    def wiki(*args, task_promotion):
        task_promotion(event)
        return dict(promoted_skills=1)
    monkeypatch.setattr(teacher,'verify',wiki)
    def run():
        report_path.write_text(json.dumps(report))
        return scoped.verify_exp_scoped_publication(root,report_path,amendment_sha256=file_hash(amendment))
    return SimpleNamespace(**locals())


def test_scoped_entry_replays_selected_receipt_and_retains_both_old_slots(packet):
    f=packet; result=f.run()
    assert result['accepted'] and result['validation_45']==result['postseal_full_tests']=='not_run'
    assert len(f.calls)==1
    reader, ref, kwargs=f.calls[0]
    assert ref==f.promotion_ref
    assert kwargs['campaign_ref']==f.report['campaign_ref']
    assert kwargs['amendment_ref']==file_hash(f.amendment)
    assert kwargs['trusted_before_inventory_ref']==f.report['trusted_before_inventory_ref']
    assert kwargs['trusted_review_refs']==f.report['trusted_review_refs']
    assert set(kwargs['trials'])=={'exp','sigmoid'}
    assert all(row['reader'] is reader for row in kwargs['trials'].values())
    assert not (f.root/'release.json').exists()


@pytest.mark.parametrize('field,value', [('proposal_id','another'),('wiki_id','sigmoid-pipeline'),
    ('target_skill','skills/other/SKILL.md'),('decision','deferred')])
def test_event_cannot_substitute_other_promotion(packet,field,value):
    packet.event[field]=value
    with pytest.raises(ValueError,match='Wiki event differs'):packet.run()
    assert not packet.calls


def test_event_cannot_reuse_unrelated_receipt(packet):
    p=packet.directory/'unrelated.json';p.write_text('{}')
    packet.event['validation_receipt']=teacher.source(p,packet.repo.parent)
    with pytest.raises(ValueError,match='another promotion'):packet.run()


@pytest.mark.parametrize('defect', ['amendment','omitted_sigmoid','tampered_index','invalid_machine','invalid_promotion'])
def test_rejects_scope_or_evidence_join_changes(packet,defect):
    f=packet
    if defect=='amendment':
        v=json.loads(f.amendment.read_text());v['validation_45']='passed';f.amendment.write_text(json.dumps(v))
        f.report['amendment']=pointer(f.amendment)
    elif defect=='omitted_sigmoid':del f.report['trials']['sigmoid']
    elif defect=='tampered_index':f.index.write_text('{}')
    elif defect=='invalid_machine':f.outcome['machine']['verdict']='rejected'
    else:f.outcome['eligible_for_teacher_edit']=False
    with pytest.raises(ValueError):f.run()


def test_explicit_amendment_hash_is_required(packet):
    f=packet;f.report_path.write_text(json.dumps(f.report))
    with pytest.raises(ValueError,match='caller-trusted'):
        scoped.verify_exp_scoped_publication(f.root,f.report_path,amendment_sha256='sha256:'+'0'*64)


def test_actual_leaf_rejection_propagates(packet,monkeypatch):
    def reject(*args,**kwargs):raise ValueError('raw Task/profile rejected')
    monkeypatch.setattr(sys.modules['task_rule_gate_completion_admission'],'verify_continuation_promotion',reject)
    with pytest.raises(ValueError,match='raw Task/profile rejected'):packet.run()


def test_bound_local_handoff_does_not_override_indexed_retained_bytes(packet):
    from aprof_runtime.store import _ReadOnlyArtifacts,default_object_directory
    f=packet; ref=f.promotion_ref; payload=f.local.verify_artifact(ref).read_bytes()
    root=default_object_directory(f.db); object_path=root/'sha256'/ref[7:9]/ref[9:]
    object_path.parent.mkdir(parents=True);object_path.write_bytes(payload)
    connection=sqlite3.connect(f.db);connection.execute('INSERT INTO artifacts VALUES(?)',(ref,));connection.commit()
    f.local._paths[ref]=f.directory/'absent'
    reader=scoped._PublicationReader([_ReadOnlyArtifacts(connection,root)],[f.local],{})
    assert reader.verify_artifact(ref)==object_path
    object_path.write_bytes(b'tamper')
    with pytest.raises(Exception,match='corrupt'):reader.verify_artifact(ref)
    connection.close()


@pytest.mark.parametrize('version,validation,measurement,report,amendment', [
    ('0.5.1',None,None,'report','sha256:'+'1'*64),
    ('1.0.0','old45',None,'report','sha256:'+'1'*64),
    ('1.0.0',None,'oldmethod','report','sha256:'+'1'*64),
    ('1.0.0',None,None,'report',None),('1.0.0',None,None,None,'sha256:'+'1'*64)])
def test_new_release_branch_has_no_implicit_waiver(tmp_path,version,validation,measurement,report,amendment):
    with pytest.raises(ValueError,match='explicit amendment hash'):
        release.publication_evidence(tmp_path/'graph-base'/version,validation,measurement,
            scoped_publication=report,scope_amendment_sha256=amendment)


def test_release_branch_requires_replayed_acceptance(tmp_path,monkeypatch):
    monkeypatch.setattr(scoped,'verify_exp_scoped_publication',lambda *a,**k:dict(accepted=False))
    with pytest.raises(ValueError,match='independently replayed'):
        release.publication_evidence(tmp_path/'graph-base/1.0.0',None,
            scoped_publication='report',scope_amendment_sha256='sha256:'+'1'*64)


def wiki_fixture(tmp_path,monkeypatch):
    repo=tmp_path/'repo';root=repo/'skill-libs/graph-base/1.0.0'
    (root/'wiki').mkdir(parents=True);(root/'skillgraph/versions/v0002').mkdir(parents=True)
    target='skills/ascendc-aprof-optimization/SKILL.md'
    (root/target).parent.mkdir(parents=True);(root/target).write_text('new conditional rule\n')
    traces=repo.parent/'optimization-traces';traces.mkdir();(traces/'index.json').write_text('{}')
    split=repo/'scaffolding/benchmarks/cannbench/split_index.json';split.parent.mkdir(parents=True);split.write_text('{}')
    actual={'history':dict(level=1,operator='exp',split='train',sources=[dict(sha256='source')])}
    audit={'trace_index_sha256':file_hash(traces/'index.json'),'split_index_sha256':file_hash(split),
           'records':{'history':dict(actual['history'],decision='include',reason='scope',wiki_ids=['exp-tile8192'])}}
    audit_path=repo/'audit.json';audit_path.write_text(json.dumps(audit))
    entry=dict(page='exp-tile8192.md',status='validated',skill_refs=[target],source_keys=['history'],
        source_refs=[dict(key='history',sha256=['source'])],toolchain_scope='910C/A3 CANN9',graph_nodes=[])
    (root/'wiki/index.json').write_text(json.dumps({'entries':{'exp-tile8192':entry}}))
    (root/'wiki/exp-tile8192.md').write_text('## 适用条件\n## 证据与反例\n## 验证与结论\n')
    event=dict(wiki_id='exp-tile8192',decision='accepted',reason='independent evidence')
    (root/'wiki/evolution.jsonl').write_text(json.dumps(event)+'\n')
    graph=dict(graph_version='v0002',anchors=[],predicates=[],mechanisms=[],transformations=[])
    (root/'skillgraph/versions/v0002/graph.json').write_text(json.dumps(graph))
    monkeypatch.setattr(teacher,'verify_frozen_machine_rules',lambda *args:None)
    monkeypatch.setattr(teacher,'inventory',lambda *args:actual)
    result=dict(valid=True,operator='exp',eligible_for_teacher_edit=True,
                edit=dict(target_skill=target,applied=True,before='before',after=file_hash(root/target)))
    def verify():return teacher.verify(repo,traces,root,audit_path,task_promotion=lambda event:result)
    return SimpleNamespace(**locals())


def test_teacher_scoped_branch_still_checks_actual_skill_revision(tmp_path,monkeypatch):
    f=wiki_fixture(tmp_path,monkeypatch)
    assert f.verify()['promoted_skills']==1
    (f.root/f.target).write_text('tampered after promotion')
    with pytest.raises(ValueError,match='published skill differs'):f.verify()


def test_teacher_scoped_branch_does_not_drop_split_isolation(tmp_path,monkeypatch):
    f=wiki_fixture(tmp_path,monkeypatch)
    f.actual['history']['split']='test';f.audit['records']['history']['split']='test'
    f.audit_path.write_text(json.dumps(f.audit))
    with pytest.raises(ValueError,match='validation/test source entered Wiki'):f.verify()


def test_teacher_scoped_branch_requires_accepted_exp_only(tmp_path,monkeypatch):
    f=wiki_fixture(tmp_path,monkeypatch)
    (f.root/'wiki/evolution.jsonl').write_text('')
    index=json.loads((f.root/'wiki/index.json').read_text())
    index['entries']['exp-tile8192'].update(status='draft',skill_refs=[])
    (f.root/'wiki/index.json').write_text(json.dumps(index))
    with pytest.raises(ValueError,match='exactly one accepted exp'):f.verify()
