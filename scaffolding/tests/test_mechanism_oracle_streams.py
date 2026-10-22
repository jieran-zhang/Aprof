"""Actual subprocess stdout/stderr separation; no model or device execution."""
import json
from pathlib import Path
import sys

import pytest

from aprof_runtime.errors import StoreError
from aprof_runtime.local_evidence import LocalEvidence
import local_controller_bridge as bridge


def execute(tmp_path, *, stdout=None, result=None, code=0):
    local = LocalEvidence(tmp_path/'records')
    value = {'case_id': 3, 'passed': True}
    result = value if result is None else result
    stdout = json.dumps(value) if stdout is None else stdout
    output = tmp_path/'result.json'
    script = ('import json,sys; from pathlib import Path; '
        'Path(sys.argv[1]).write_text(sys.argv[2]); '
        'print(sys.argv[3]); print("diagnostic warning on stderr",file=sys.stderr); '
        'sys.exit(int(sys.argv[4]))')
    record = bridge.profile_capture.run([sys.executable, '-c', script, str(output),
        json.dumps(result), stdout, str(code)], tmp_path, tmp_path/'oracle', 10, local)
    return local, record, output


def test_json_stdout_accepts_independent_stderr_without_discarding_logs(tmp_path):
    local, record, output = execute(tmp_path)
    with pytest.raises(json.JSONDecodeError):
        json.loads(record['text'].strip())
    assert bridge.verify_mechanism_oracle(local, record, output, 3) == {'case_id': 3, 'passed': True}
    assert local.verify_artifact(record['stderr_hash']).read_text() == 'diagnostic warning on stderr\n'
    raw = json.loads(local.verify_artifact(record['log_hash']).read_text())
    assert raw['stdout_hash'] == record['stdout_hash'] and raw['stderr_hash'] == record['stderr_hash']
    assert raw['exit_code'] == 0


@pytest.mark.parametrize('stdout,result', [
    ('{}', None),
    ('not JSON', None),
    ('{"case_id":3,"passed":true}\n{}', None),
    (None, {'case_id': 3, 'passed': False}),
    ('{"case_id":4,"passed":true}', {'case_id': 4, 'passed': True}),
])
def test_missing_malformed_mismatched_or_failed_verdict_rejected(tmp_path, stdout, result):
    local, record, output = execute(tmp_path, stdout=stdout, result=result)
    with pytest.raises((ValueError, json.JSONDecodeError)):
        bridge.verify_mechanism_oracle(local, record, output, 3)


def test_changed_stdout_digest_rejected(tmp_path):
    local, record, output = execute(tmp_path)
    local.verify_artifact(record['stdout_hash']).write_text('{}')
    with pytest.raises(StoreError):
        bridge.verify_mechanism_oracle(local, record, output, 3)


def test_actual_nonzero_verifier_exit_remains_rejected(tmp_path):
    with pytest.raises(RuntimeError):
        execute(tmp_path, code=2)
