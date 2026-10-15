"""Record one Task rule attempt locally; the dispatcher alone binds real exit.

Use the original absolute monotonic deadline from the controller. Successful
stages follow task_rule_admission.STAGES exactly. A failure retains an unfinished
chain; no completed event is fabricated. All records and roster versions are
immutable so LocalEvidence references remain valid.
"""
from task_budget import rule_execution_job
from copy import deepcopy
import json
from pathlib import Path
import time

from shared_validation_adapter import selected_runtime
selected_runtime()
from aprof_runtime.local_evidence import LocalEvidence
from task_rule_admission import IDENTITY, PROTOCOL, STAGES, TASK_PROTOCOL
from timing_admission import number, read, require


_REPORT_KEYS = dict(correctness='correctness_report_ref', boundary='boundary_report_ref',
                    screen='screen_report_ref', task_measurement='measurement_admission_ref',
                    profile='mechanism_report_ref')
_PLAN_REFS = ('job_ref', 'input_inventory_ref', 'boundary_plan_ref', 'screen_plan_ref',
              'profile_plan_ref', 'source_review_ref')


class TaskRuleRecorder:
    """Create protocol/registration after build, then record actual local stages.

    ``post_build`` contains only binary_hashes, oracle_files, task_config_ref and
    profile_configs. ``finish()`` returns a child report reference WITHOUT an
    execution_ref. After the child exits, the dispatcher reads that report and
    registers a NEW report with its actual execution_ref; it never edits this
    recorder's files. ``expected`` supplies the other replay identity fields.
    """
    def __init__(self, store, output, *, anchor_ref, post_build, deadline):
        require(isinstance(store, LocalEvidence), 'Task recorder requires LocalEvidence')
        self.store, self.deadline = store, number(deadline)
        self._remaining()
        anchor = read(store, anchor_ref)
        require(anchor.get('schema_version') == 1 and anchor.get('protocol') == PROTOCOL
                and anchor.get('task_protocol') == TASK_PROTOCOL and anchor.get('purpose') == 'promotion'
                and anchor.get('operator') in ('exp', 'sigmoid'), 'invalid Task attempt anchor')
        require(0 < self._remaining() <= number(anchor['budget_seconds'])
                and number(anchor['created_at']) <= time.time(), 'anchor deadline/time differs')
        require(set(post_build) == {'binary_hashes', 'oracle_files', 'task_config_ref', 'profile_configs'}
                and set(post_build['binary_hashes']) == set(post_build['profile_configs']) == {'baseline', 'candidate'}
                and isinstance(post_build['oracle_files'], dict) and post_build['oracle_files'],
                'incomplete post-build Task bindings')
        require(isinstance(anchor['history_refs'], list) and anchor['history_refs']
                and len(anchor['history_refs']) == len(set(anchor['history_refs'])), 'missing attempt history')
        for reference in [*(anchor[key] for key in _PLAN_REFS), *anchor['history_refs'],
                *anchor['source_hashes'].values(), *post_build['binary_hashes'].values(),
                *post_build['oracle_files'].values(), post_build['task_config_ref'],
                *post_build['profile_configs'].values()]:
            store.verify_artifact(reference)
        require(number(read(store, anchor['job_ref'])['timeout_seconds']) == anchor['budget_seconds'],
                'anchor and actual job budget differ')
        self.output = Path(output).absolute()
        require(self.output.resolve() == self.output and self.output.is_relative_to(store.directory.parent),
                'recorder output must stay in the local task workspace')
        self.output.mkdir(mode=0o700, exist_ok=False)
        self.events, self.stage_evidence, self.bindings = [], {}, {}
        self.active, self.failed, self.failure_ref = None, False, None
        self.partial_ref, self.finished_ref = None, None
        self.protocol = dict(deepcopy(anchor), **deepcopy(post_build), anchor_ref=anchor_ref, created_at=time.time())
        launch_path = Path(read(store, anchor['controller_plan_ref'])['launch_path']) if 'controller_plan_ref' in anchor else None
        if launch_path is not None:
            launch_ref = store.register_artifact(launch_path)
            launch = read(store, launch_ref)
            rule_execution_job(lambda ref: read(store, ref), anchor, read(store, anchor['job_ref']), launch)
            require(deadline == launch['monotonic_deadline'], 'recorder changed the original deadline')
            if launch['schema_version'] == 2:
                self.protocol['dispatcher_launch_ref'] = launch_ref
        self.protocol_ref = self._save('protocol.json', self.protocol)
        self.registration = dict(schema_version=1, run_id=anchor['run_id'], candidate_id=anchor['candidate_id'],
            anchor_ref=anchor_ref, protocol_ref=self.protocol_ref, created_at=time.time(), max_attempts=1,
            stop_on_failure=True, resampling='none', stages=list(STAGES))
        self.registration_ref = self._save('registration.json', self.registration)
        self.expected = {key: deepcopy(anchor[key]) for key in IDENTITY}
        self.expected.update(anchor_ref=anchor_ref, protocol_ref=self.protocol_ref,
                             qualification_registration_ref=self.registration_ref)
        self._roster()
        try:
            self._remaining()
        except Exception as error:
            self._stop(error)
            raise

    def _remaining(self):
        value = self.deadline - time.monotonic()
        if value <= 0:
            raise TimeoutError('original Task controller deadline expired')
        return value

    def _save(self, name, value):
        path = self.output / name
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8') as stream:
            json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write('\n')
        return self.store.register_artifact(path)

    def _roster(self):
        self.roster_ref = self._save(f'attempt-rosters/{len(self.events):02d}.json',
            dict(schema_version=1, registration_ref=self.registration_ref, events=list(self.events)))

    def _open(self):
        require(not self.failed and self.finished_ref is None, 'Task recorder is already terminal')
        self._remaining()

    def _event(self, stage, state, evidence=()):
        sequence = len(self.events)
        require(sequence < 2 * len(STAGES) and stage == STAGES[sequence // 2]
                and state == ('started' if sequence % 2 == 0 else 'completed'),
                'controller attempted an unregistered or repeated Task stage')
        event = dict(sequence=sequence, previous_ref=self.events[-1] if self.events else self.registration_ref,
            registration_ref=self.registration_ref, stage=stage, state=state,
            at=time.time(), evidence_refs=list(evidence))
        if state == 'completed':
            event['exit_status'] = 0
        self.events.append(self._save(f'stage-events/{sequence:02d}.json', event))
        self.active = stage if state == 'started' else None
        self._roster()

    def _report(self):
        return dict(schema_version=1, protocol=PROTOCOL, **deepcopy(self.expected),
            attempt_roster_ref=self.roster_ref, stage_evidence=deepcopy(self.stage_evidence), **self.bindings)

    def partial_report(self):
        """Retain an incomplete report, without pretending the child exited."""
        require(self.failed, 'partial reports are only for stopped attempts')
        if self.partial_ref is None:
            self.partial_ref = self._save('partial-report.json', self._report())
        return self.partial_ref

    def _stop(self, error, evidence=()):
        if self.failed or self.finished_ref is not None:
            return
        self.failed = True
        self.failure_ref = self._save('stage-failure.json', {'type': type(error).__name__, 'message': str(error)})
        if self.active is not None:
            self.stage_evidence[self.active] = list(dict.fromkeys([self.failure_ref, *evidence]))
        self.partial_report()

    def start(self, stage):
        try:
            self._open()
            self._event(stage, 'started')
            self._remaining()
        except Exception as error:
            self._stop(error)
            raise

    def complete(self, stage, evidence, *, report_ref=None, passed=True):
        verified = []
        try:
            self._open()
            require(self.active == stage and isinstance(evidence, (list, tuple)) and evidence
                    and len(evidence) == len(set(evidence)), 'missing or repeated Task stage evidence')
            for reference in evidence:
                self.store.verify_artifact(reference)
                verified.append(reference)
            require(passed is True, 'Task stage failed; no retry')
            if stage in _REPORT_KEYS:
                require(report_ref in verified, 'stage must bind its actual component report')
            else:
                require(report_ref is None, 'online admission has no replacement component report')
            self._remaining()
            self._event(stage, 'completed', verified)
            self.stage_evidence[stage] = verified
            if report_ref is not None:
                self.bindings[_REPORT_KEYS[stage]] = report_ref
            self._remaining()
        except Exception as error:
            self._stop(error, verified)
            raise

    def fail_active(self, error, evidence=()):
        """Retain real failure/partial artifacts even after the deadline expires."""
        verified = []
        try:
            for reference in evidence:
                self.store.verify_artifact(reference)
                verified.append(reference)
        finally:
            self._stop(error, verified)
        return self.partial_ref

    def finish(self):
        """Return only the complete child evidence report, never an exit verdict."""
        try:
            self._open()
            require(self.active is None and len(self.events) == 2 * len(STAGES)
                    and set(self.stage_evidence) == set(STAGES), 'Task stage chain is incomplete')
            reference = self._save('child-report.json', self._report())
            self._remaining()
            self.finished_ref = reference
            return reference
        except Exception as error:
            self._stop(error)
            raise
