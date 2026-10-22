"""Native IEEE metadata compatibility; CPU oracle fixtures, never NPU evidence."""
import json
import math
from pathlib import Path
import shutil
import time

import pytest

import task_rule_correctness as driver
import archived_rule_correctness as archived
from archive_task_rule_sources import archive_task_rule_sources
from aprof_runtime.store import EpisodeStore
from verify_measurement_publication import ReadonlyCAS


SPECIAL_CASES = [('exp', 12), ('sigmoid', 12), ('sigmoid', 13)]


def original_metadata(operator, case):
    path = driver.adapter.ROUND / operator / 'prepared' / f'case_{case:02d}/metadata.json'
    return path, json.loads(path.read_text())


@pytest.mark.parametrize('operator,case', SPECIAL_CASES)
def test_original_metadata_roundtrip_preserves_every_field(tmp_path, operator, case):
    original, value = original_metadata(operator, case)
    before = original.read_bytes()
    assert any(not math.isfinite(v) for v in value['value_range'])
    output = tmp_path / 'role-output.bin'
    target = tmp_path / 'metadata.json'
    driver._write_native_metadata(target, value, output)
    actual = json.loads(target.read_text(), parse_constant=lambda token: float(token))
    assert driver._same_native_metadata(actual, dict(value, output=str(output)))
    assert original.read_bytes() == before
    assert value['output'] != str(output)
    with pytest.raises(FileExistsError):
        driver._write_native_metadata(target, value, output)
    # The general report writer still rejects precisely the native special data.
    with pytest.raises(ValueError, match='JSON compliant'):
        driver.bridge.save(tmp_path / 'report.json', {'native': value})


@pytest.mark.parametrize('replacement', [None, 'nan', math.inf, -math.inf, 0.0])
def test_nan_comparison_does_not_coerce_other_values(replacement):
    left = {'nested': [float('nan'), {'range': [-math.inf, math.inf]}]}
    equal = {'nested': [float('nan'), {'range': [-math.inf, math.inf]}]}
    assert driver._same_native_metadata(left, equal)
    assert archived._same_native_metadata is driver._same_native_metadata
    equal['nested'][0] = replacement
    assert not driver._same_native_metadata(left, equal)


@pytest.mark.parametrize('changed', [
    {'n': 1.0}, {'n': True}, {'n': '1'}, {'n': 1, 'extra': None}, {'n': [1]},
])
def test_native_comparison_preserves_types_and_roster(changed):
    assert not driver._same_native_metadata({'n': 1}, changed)


@pytest.mark.parametrize('operator', ['exp', 'sigmoid'])
def test_collect_and_online_archived_replay_with_original_special_ranges(tmp_path, monkeypatch, operator):
    import task_correctness_cpu_fixture as fixture
    workspace = tmp_path / 'task'
    workspace.mkdir()
    original_dump = fixture.dump
    special = {case: original_metadata(operator, case)[1]
               for op, case in SPECIAL_CASES if op == operator}

    def dump(path, value):
        # Tiny CPU inputs/shape remain fixture-owned. Copy the actual native
        # special ranges before their first write/index, never alter old inputs.
        if path.name == 'metadata.json' and path.parent.parent.name == 'prepared':
            source = special.get(value['case_id'])
            if source:
                value = dict(value, value_range=source['value_range'])
                if operator == 'exp':
                    value.update({k: source[k] for k in ('base', 'scale', 'shift')})
        return original_dump(path, value)

    monkeypatch.setattr(fixture, 'dump', dump)
    args, protocol = fixture.fixture(workspace, operator)
    local = args['store']
    protocol['source_review_ref'] = local.register_artifact(args['assembly'] / 'source-review.json')
    args['protocol_ref'] = local.register_json(protocol)
    executor = fixture.CPUExecutor(operator)
    monkeypatch.setattr(driver.bridge.profile_capture, 'run', executor)
    result = driver.collect_correctness(**args, destination=workspace / 'correctness',
                                        deadline=time.monotonic() + 120)
    assert result['status'] == 'passed' and len(executor.calls) == 80
    kwargs = dict(protocol_ref=args['protocol_ref'], expected=args['expected'],
                  window=[result['started_at'], result['finished_at']])
    assert driver.verify_rule_correctness(local, result['report_ref'], **kwargs)['case_count'] == 20
    report = driver.read(local, result['report_ref'])
    for row in report['rows']:
        if row['case_id'] in special:
            bound = json.loads(local.verify_artifact(row['metadata_ref']).read_text())
            assert driver._same_native_metadata(bound['value_range'], special[row['case_id']]['value_range'])

    # A fresh object reference cannot hide a semantic change from either reader.
    changed = json.loads(json.dumps(report))
    row = next(row for row in changed['rows'] if row['case_id'] in special)
    bound = json.loads(local.verify_artifact(row['metadata_ref']).read_text())
    bound['value_range'] = [0.0, 0.0]
    row['metadata_ref'] = local.register_json(bound)
    changed_ref = local.register_json(changed)
    with pytest.raises(ValueError, match='row source/input/output'):
        driver.verify_rule_correctness(local, changed_ref, **kwargs)

    database = tmp_path / 'archive.sqlite'
    index = json.loads(local.write_index(workspace / 'local-index.json').read_text())
    with EpisodeStore(database) as store:
        for reference in index['artifacts']:
            assert store.register_artifact(local.verify_artifact(reference)) == reference
        source_ref = archive_task_rule_sources(local, result['report_ref'], store)
    shutil.rmtree(workspace)
    reader = ReadonlyCAS(database)
    try:
        replay = archived.verify_archived_rule_correctness(reader, result['report_ref'],
            source_archive_ref=source_ref, **kwargs)
        assert replay['passed'] and replay['case_count'] == 20
        with pytest.raises(ValueError, match='row source/input/output'):
            archived.verify_archived_rule_correctness(reader, changed_ref,
                source_archive_ref=source_ref, **kwargs)
    finally:
        reader.connection.close()
