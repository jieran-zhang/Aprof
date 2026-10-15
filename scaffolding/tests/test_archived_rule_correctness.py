"""Real original CPU oracle -> post-task collection -> remove fixture workspace.

The kernel/build executor is explicitly synthetic; no NPU/profile is produced.
"""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time

import pytest

REPO=Path(__file__).resolve().parents[2]
for path in (REPO/'scaffolding/collection/scripts', REPO/'scaffolding/tools'):
    sys.path.insert(0,str(path))
import archived_rule_correctness as driver
from archive_task_rule_sources import archive_task_rule_sources
from aprof_runtime.store import EpisodeStore
from aprof_runtime.traces import register_json_artifact
from verify_measurement_publication import ReadonlyCAS

import task_correctness_cpu_fixture as fixture_module

@pytest.fixture(scope='module')
def retained(tmp_path_factory):
    root=tmp_path_factory.mktemp('archived-correctness');workspace=root/'task';workspace.mkdir()
    # The existing genuine oracle fixture uses the same trusted screen-enabled
    # source generator as the current outer controller; only execution is CPU.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(fixture_module,'adapter',driver.screen.rule)
        patch.setattr(fixture_module,'bridge',driver.screen.bridge)
        patch.setattr(fixture_module.driver,'adapter',driver.screen.rule)
        patch.setattr(fixture_module.driver,'bridge',driver.screen.bridge)
        args,protocol=fixture_module.fixture(workspace,'exp')
        protocol['source_review_ref']=args['store'].register_artifact(args['assembly']/'source-review.json')
        args['protocol_ref']=args['store'].register_json(protocol)
        executor=fixture_module.CPUExecutor('exp')
        patch.setattr(driver.screen.bridge.profile_capture,'run',executor)
        result=fixture_module.driver.collect_correctness(**args,destination=workspace/'correctness',deadline=time.monotonic()+120)
        assert result['status']=='passed' and len(executor.calls)==80
        boundary_args=dict(args, prepared=driver.screen.rule.ROUND/'exp/boundary-inputs')
        boundary=fixture_module.driver.collect_correctness(**boundary_args, destination=workspace/'boundary',
            deadline=time.monotonic()+120, stage='boundary')
        assert boundary['status']=='passed' and len(executor.calls)==80+42*4
    store_path=root/'retained.sqlite'
    index=args['store'].write_index(workspace/'local-index.json')
    with EpisodeStore(store_path) as archive:
        for reference in json.loads(index.read_text())['artifacts']:
            assert archive.register_artifact(args['store'].verify_artifact(reference))==reference
        source_ref=archive_task_rule_sources(args['store'],result['report_ref'],archive)
    kwargs=dict(protocol_ref=args['protocol_ref'],expected=args['expected'],window=[result['started_at'],result['finished_at']],source_archive_ref=source_ref)
    (root/'boundary-test-binding.json').write_text(json.dumps({'report_ref':boundary['report_ref'],
        'window':[boundary['started_at'],boundary['finished_at']]}))
    shutil.rmtree(workspace)
    assert not workspace.exists()
    return store_path,result['report_ref'],kwargs,root


def invoke(retained):
    path,reference,kwargs,_=retained
    reader=ReadonlyCAS(path)
    try:return driver.verify_archived_rule_correctness(reader,reference,**kwargs)
    finally:reader.connection.close()


def test_full_twenty_both_roles_original_oracle_after_tmp_removed(retained):
    result=invoke(retained)
    assert result['passed'] and result['case_count']==20
    assert result['admission_authority'] is False and result['eligible_for_publication'] is False


@pytest.mark.parametrize('kind',['source','input','output'])
@pytest.mark.parametrize('damage',['missing','corrupt'])
def test_absent_or_changed_archived_bytes_are_rejected(retained,kind,damage):
    database,ref,kwargs,root=retained;reader=ReadonlyCAS(database)
    report=driver.read(reader,ref)
    if kind=='source':
        proof=driver.read(reader,report['source_review_ref']);digest=proof['adapted_files']['op_host/exp.asc']
    elif kind=='input':digest=next(iter(report['rows'][0]['input_refs'].values()))
    else:digest=report['rows'][0]['output_refs'][0]
    path=reader.verify_artifact(digest);reader.connection.close()
    assert path.is_relative_to(root)
    original=path.read_bytes();aside=path.with_name(path.name+'.test-only-missing')
    try:
        if damage=='missing':path.rename(aside)
        else:path.write_bytes(b'changed'+original[7:])
        with pytest.raises(ValueError):invoke(retained)
    finally:
        if damage=='missing':aside.rename(path)
        else:path.write_bytes(original)


def changed_refs(retained,kind):
    database,ref,kwargs,_=retained;reader=ReadonlyCAS(database)
    report=driver.read(reader,ref);protocol=driver.read(reader,kwargs['protocol_ref'])
    supplement=driver.read(reader,kwargs['source_archive_ref'])
    inventory=driver.read(reader,protocol['input_inventory_ref']);reader.connection.close()
    kwargs=deepcopy(kwargs)
    with EpisodeStore(database) as store:
        if kind=='source_map':
            supplement['files'].pop(next(iter(supplement['files'])))
            kwargs['source_archive_ref']=register_json_artifact(store,supplement)
        elif kind=='case_path':
            path=next(p for p in inventory if p.endswith('/case_01/metadata.json'))
            inventory[path.replace('/case_01/','/case_99/')]=inventory.pop(path)
            protocol['input_inventory_ref']=register_json_artifact(store,inventory)
            kwargs['protocol_ref']=register_json_artifact(store,protocol)
            report['protocol_ref']=kwargs['protocol_ref'];report['input_inventory_ref']=protocol['input_inventory_ref']
            ref=register_json_artifact(store,report)
        elif kind=='original_argv':
            row=report['rows'][0]
            record=driver.read(store,row['verifier_execution_ref'])
            record['argv']=[*record['argv'][:-1],'/other/metadata.json']
            row['verifier_execution_ref']=register_json_artifact(store,record)
            ref=register_json_artifact(store,report)
    return database,ref,kwargs,retained[3]


@pytest.mark.parametrize('kind',['source_map','case_path','original_argv'])
def test_mapping_or_execution_cannot_substitute_original_evidence(retained,kind):
    with pytest.raises(ValueError):invoke(changed_refs(retained,kind))


def test_full_boundary_original_oracle_after_tmp_removed(retained):
    path, _, kwargs, root = retained
    binding = json.loads((root / 'boundary-test-binding.json').read_text())
    reader = ReadonlyCAS(path)
    try:
        result = driver.verify_archived_rule_correctness(reader, binding['report_ref'],
            **dict(kwargs, window=binding['window']))
    finally:
        reader.connection.close()
    assert result['passed'] and result['stage'] == 'boundary' and result['case_count'] == 42
    assert not result['admission_authority'] and not result['eligible_for_publication']
