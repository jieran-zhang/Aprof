"""Read-only publication entry for the explicitly authorized Exp continuation.

The amendment waives the 45-run comparison and post-seal test sweep only for
this scope. Original raw evidence and the new continuation are replayed by the
current trusted verifiers; no code is executed from an evidence archive.
"""
from contextlib import ExitStack
import json
from pathlib import Path
import re
import sqlite3
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scaffolding/collection/scripts'))

REPORT_KEYS = {'schema_version', 'kind', 'release_id', 'amendment', 'campaign_ref',
    'promotion_ref', 'trusted_before_inventory_ref', 'archives', 'local_indices',
    'trials', 'trusted_review_refs', 'teacher_audit'}
SCOPE = {'schema_version': 1, 'kind': 'teacher_exp_only_scope_amendment',
    'authorization': 'user_requested_exp_only_release_on_success',
    'release_id': 'graph-base/1.0.0',
    'target': {'device': '910C', 'architecture': 'A3', 'cann_version': '9.0.0'},
    'operators': ['exp'], 'validation_45': 'not_run',
    'postseal_full_tests': 'not_run', 'other_rules': 'draft'}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _pointer(pointer):
    from aprof_runtime.jsonio import file_hash
    _require(isinstance(pointer, dict) and set(pointer) == {'path', 'sha256'}
             and isinstance(pointer['path'], str)
             and isinstance(pointer['sha256'], str)
             and re.fullmatch(r'sha256:[0-9a-f]{64}', pointer['sha256']),
             'publication requires an exact path/hash pointer')
    path = Path(pointer['path'])
    _require(path.is_absolute() and path.resolve() == path and not path.is_symlink()
             and path.is_file() and file_hash(path) == pointer['sha256'],
             'publication attachment changed or is not a canonical regular file')
    return path


class _PublicationReader:
    """Indexed retained CAS first; only explicitly bound new local handoffs next."""
    def __init__(self, archives, local, attachments):
        self.archives, self.local, self.attachments = archives, local, attachments

    def verify_artifact(self, reference):
        _require(isinstance(reference, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', reference),
                 'invalid publication artifact reference')
        for reader in self.archives:
            if reader.connection.execute('SELECT 1 FROM artifacts WHERE content_hash=?', (reference,)).fetchone():
                return reader.verify_artifact(reference)
        for reader in self.local:
            if reference in reader._paths:
                return reader.verify_artifact(reference)
        if reference in self.attachments:
            return _pointer(self.attachments[reference])
        raise ValueError('publication evidence is not indexed: ' + reference)


def verify_exp_scoped_publication(release, report_path, *, amendment_sha256):
    from verify_teacher_wiki import verify, verify_frozen_machine_rules, verify_promotion_runtime, checked_file
    release, report_path = Path(release).resolve(), Path(report_path).resolve(strict=True)
    _require(release == REPO / 'skill-libs/graph-base/1.0.0', 'exp scope requires canonical graph-base/1.0.0')
    verify_frozen_machine_rules(REPO, release)
    verify_promotion_runtime(release)
    sys.path.insert(0, str(release / 'runtime/src'))
    from aprof_runtime.jsonio import file_hash
    from aprof_runtime.local_evidence import LocalEvidence
    from aprof_runtime.store import _ReadOnlyArtifacts, default_object_directory
    from task_rule_gate_completion_admission import verify_continuation_promotion
    from timing_admission import number
    verify_promotion_runtime(release, require_loaded=True)

    report_hash = file_hash(report_path)
    report = json.loads(report_path.read_text())
    _require(isinstance(report, dict) and set(report) == REPORT_KEYS
             and report['schema_version'] == 1 and report['kind'] == 'exp_scoped_publication_v1'
             and report['release_id'] == SCOPE['release_id'], 'unsupported scoped publication report')
    amendment_path = _pointer(report['amendment'])
    _require(report['amendment']['sha256'] == amendment_sha256, 'caller-trusted scope amendment differs')
    amendment = json.loads(amendment_path.read_text())
    _require(set(amendment) == set(SCOPE) | {'created_at'}
             and all(amendment[key] == value for key, value in SCOPE.items())
             and number(amendment['created_at']) > 0, 'unsupported exp-only publication amendment')
    audit_path = _pointer(report['teacher_audit'])
    _require(audit_path == REPO / 'scaffolding/curation/graph-base-1.0.0.json', 'publication changed the canonical Teacher audit')
    _require(isinstance(report['archives'], list) and report['archives']
             and isinstance(report['local_indices'], list), 'publication requires explicit retained archives and local handoffs')
    _require(set(report['trials']) == {'exp', 'sigmoid'}
             and set(report['trials']['exp']) == {'index_ref', 'dispatcher_result_ref', 'source_archive_ref'}
             and set(report['trials']['sigmoid']) == {'index_ref', 'not_run_ref'},
             'original failed Exp and unstarted Sigmoid closure must both be retained')
    _require(set(report['trusted_review_refs']) == {'archive_inventory_ref', 'producer_snapshot_ref'},
             'publication requires the trusted original review archive identities')
    pointers = [report['amendment'], report['teacher_audit'], *report['archives'], *report['local_indices']]
    paths = [_pointer(pointer) for pointer in pointers]
    _require(len(paths) == len(set(paths)), 'duplicate publication attachment')
    with ExitStack() as stack:
        archives = []
        for pointer in report['archives']:
            database = _pointer(pointer)
            connection = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)
            stack.callback(connection.close)
            archives.append(_ReadOnlyArtifacts(connection, default_object_directory(database)))
        locals_ = [LocalEvidence.from_index(_pointer(pointer)) for pointer in report['local_indices']]
        reader = _PublicationReader(archives, locals_, {p['sha256']: p for p in pointers})
        for ref in (report['campaign_ref'], report['promotion_ref'], report['trusted_before_inventory_ref'],
                    *report['trusted_review_refs'].values()):
            reader.verify_artifact(ref)
        promotion = json.loads(reader.verify_artifact(report['promotion_ref']).read_text())
        _require(promotion.get('kind') == 'teacher_exp_continuation_promotion'
                 and promotion.get('wiki_id') == 'exp-tile8192'
                 and promotion.get('amendment_ref') == amendment_sha256
                 and promotion.get('campaign_ref') == report['campaign_ref'],
                 'publication selected a different continuation or rule')
        trials = {operator: dict(values, reader=reader) for operator, values in report['trials'].items()}
        verified = []

        def replay(event):
            _require(event.get('decision') == 'accepted'
                     and all(event.get(key) == promotion.get(key) for key in ('proposal_id', 'wiki_id', 'target_skill')),
                     'accepted Wiki event differs from the selected promotion')
            receipt = checked_file(event.get('validation_receipt'), REPO.parent)
            _require(file_hash(receipt) == report['promotion_ref'], 'accepted event binds another promotion receipt')
            result = verify_continuation_promotion(reader, report['promotion_ref'],
                campaign_ref=report['campaign_ref'], trials=trials, amendment_ref=amendment_sha256,
                trusted_before_inventory_ref=report['trusted_before_inventory_ref'], repo=REPO, release=release,
                trusted_review_refs=report['trusted_review_refs'])
            _require(result.get('valid') is True and result.get('operator') == 'exp'
                     and result.get('eligible_for_teacher_edit') is True
                     and result.get('machine', {}).get('verdict') == 'production_safe_gain',
                     'continuation did not independently admit the Exp edit')
            verified.append(result)
            return result

        teacher = verify(REPO, REPO.parent / 'optimization-traces', release, audit_path, task_promotion=replay)
        _require(len(verified) == 1 and teacher['promoted_skills'] == 1, 'exactly one applied Exp skill revision is required')
        for pointer in pointers:
            _pointer(pointer)
        _require(file_hash(report_path) == report_hash, 'publication report changed during replay')
        return {'accepted': True, 'scope': 'exp_only_910c_a3_cann900', 'amendment_ref': amendment_sha256,
            'publication_report': {'path': str(report_path), 'sha256': report_hash},
            'validation_45': 'not_run', 'postseal_full_tests': 'not_run', 'other_rules': 'draft',
            'teacher': teacher, 'teacher_audit': report['teacher_audit'], 'promotion': verified[0],
            'new_hardware_executed': False, 'archive_performed': False}
