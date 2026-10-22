"""Recheck one retained review using current verifier code and pinned old bytes.

No archived Python is imported or executed. The caller independently trusts the
prelaunch anchor, source-review digest and post-task archive/snapshot digests.
Only small source/reviewer inputs are materialized in a fresh private directory;
original absolute paths remain unchanged in all receipts. A passing review does
not repair a failed trial or grant optimization/promotion/publication authority.
"""
import ast
import hashlib
import json
from pathlib import Path
import tempfile

from timing_admission import file_hash, read, require


# Only these complete producer tuples have an explicitly reviewed replay contract.
# New source revisions require a new exact tuple, never a per-file allowlist.
PRODUCER_ORDER = ('qualify_eval_tools.py', 'eval_tool_broker.py', 'isolated_eval_worker.py',
                  'eval_candidate_evidence.py', 'review_packet.py')
PRODUCER_SETS = (
    ('sha256:86c2f770fdc9e296a7397c4470de87bc3f0fe36aafcd1d1b4b04a165737a59bb',
     'sha256:22dcaaf4c90180db0a1e0d0c5c7c8f2e3f092e7bd97c1ef34cf34c313f547dcb',
     'sha256:f05216d1ae03a3b71b4ae4b763007341a37e87a36c8634b8673a63079b60a9c3',
     'sha256:9e992f0b7c76c809ead6083dceb39b76323d073a6a24dc197f2ce18429756471',
     'sha256:475d69d18ff32f6fd8322c9a85226ee0fa8a210c0cc4acf6399184185949a9f8'),
    ('sha256:86c2f770fdc9e296a7397c4470de87bc3f0fe36aafcd1d1b4b04a165737a59bb',
     'sha256:92043f4b27c1f8fcfaed965c51fb08a2a37644e12c5238af0eb1ec303d145a58',
     'sha256:f05216d1ae03a3b71b4ae4b763007341a37e87a36c8634b8673a63079b60a9c3',
     'sha256:9e992f0b7c76c809ead6083dceb39b76323d073a6a24dc197f2ce18429756471',
     'sha256:475d69d18ff32f6fd8322c9a85226ee0fa8a210c0cc4acf6399184185949a9f8'),
    ('sha256:897f197a7856d825f24ad69d0ddb01041392e35a8fb4165b0d88ee540238bca8',
     'sha256:92043f4b27c1f8fcfaed965c51fb08a2a37644e12c5238af0eb1ec303d145a58',
     'sha256:f05216d1ae03a3b71b4ae4b763007341a37e87a36c8634b8673a63079b60a9c3',
     'sha256:baf58596929f02d3f5abd595eab1393026a4e895b704a29effb7132bac3f1cc0',
     'sha256:475d69d18ff32f6fd8322c9a85226ee0fa8a210c0cc4acf6399184185949a9f8'),
    ('sha256:897f197a7856d825f24ad69d0ddb01041392e35a8fb4165b0d88ee540238bca8',
     'sha256:92043f4b27c1f8fcfaed965c51fb08a2a37644e12c5238af0eb1ec303d145a58',
     'sha256:85e57d8105c51a90d7cb1fdba8d938e44f272596edcdadc4bfd6c7ef35d7e547',
     'sha256:baf58596929f02d3f5abd595eab1393026a4e895b704a29effb7132bac3f1cc0',
     'sha256:5490040a008b76f8650ac1cb144fa10108b447c2c056bebb87ec00e67ce1d126'),
    ('sha256:897f197a7856d825f24ad69d0ddb01041392e35a8fb4165b0d88ee540238bca8',
     'sha256:92043f4b27c1f8fcfaed965c51fb08a2a37644e12c5238af0eb1ec303d145a58',
     'sha256:85e57d8105c51a90d7cb1fdba8d938e44f272596edcdadc4bfd6c7ef35d7e547',
     'sha256:c1e86ceb6671fcca7ad2d3da0dc08beaf30d0f39e36650d9bde3928f69c21936',
     'sha256:5490040a008b76f8650ac1cb144fa10108b447c2c056bebb87ec00e67ce1d126'),
)
CODEX_HASH = 'sha256:298d3d73d0bbc1367e58a370df5b6216fe30ce0a92e8b6b0afb0377a958dc335'


def _path(value):
    require(isinstance(value, str) and '\0' not in value and Path(value).is_absolute()
            and Path(value).as_posix() == value and '..' not in Path(value).parts, 'invalid retained logical path')
    return Path(value)


class _RetainedReview:
    def __init__(self, reader, *, anchor_ref, review_ref, archive_ref, producer_snapshot_ref, temporary):
        self.reader, self.temporary = reader, Path(temporary)
        self.materialized, self.original = {}, {}
        self.anchor = read(reader, anchor_ref)
        self.plan = read(reader, self.anchor['controller_plan_ref'])
        self.frozen = read(reader, self.plan['frozen_files_ref'])
        self.archive = read(reader, archive_ref)
        snapshot = read(reader, producer_snapshot_ref)
        self.files = self.archive['files']
        require(self.archive.get('owner') == snapshot.get('owner') == 'trace_collection'
                and self.archive.get('cost_scope') == snapshot.get('cost_scope') == 'post_task'
                and self.archive['producer_index_ref']['sha256'] == producer_snapshot_ref
                and snapshot['kind'] == 'frozen_task_producer_source_archive', 'untrusted post-task source provenance')
        op = self.anchor['operator']; root = _path(self.plan['directory'])
        require(self.anchor.get('schema_version') == self.plan.get('schema_version') == 1
                and self.anchor.get('protocol') == 'rule_task_admission_v1'
                and self.anchor.get('task_protocol') == 'shared_buffer_msprof_task_window_v5'
                and self.anchor.get('purpose') == 'promotion' and op in ('exp', 'sigmoid')
                and self.plan['model'] == {'name':'gpt-6-sol','reasoning_effort':'max'}
                and snapshot['source_anchors'][op] == {'path':str(root/'anchor.json'),'sha256':anchor_ref}
                and snapshot['frozen_files_refs'][op] == self.plan['frozen_files_ref'],
                'producer snapshot is not bound to this prelaunch plan')
        self.qualification_ref = self.plan['worker_qualification']
        require(self.frozen[self.qualification_ref['path']] == self.qualification_ref['sha256'],
                'qualification was not frozen before launch')
        qualification = json.loads(self.checked(self.qualification_ref).read_text())
        self.producers, self.binary = qualification['producers'], qualification['binary']
        require([Path(p['path']).name for p in self.producers] == list(PRODUCER_ORDER), 'producer roster differs')
        require(tuple(p['sha256'] for p in self.producers) in PRODUCER_SETS
                and self.binary['sha256'] == CODEX_HASH and Path(self.binary['path']).name == 'codex',
                'unknown executed producer/binary version requires an explicit compatibility review')
        scripts = _path(self.plan['release']).parents[2] / 'scaffolding/collection/scripts'
        for pointer in self.producers:
            path = pointer['path']; require(path == str(scripts/Path(path).name), 'executed producer path differs')
            retained = snapshot['files'][path]
            require(self.frozen[path] == pointer['sha256'] == retained['sha256']
                    and retained == self.files[path], 'producer bytes differ across plan/qualification/snapshot')
            self.checked(pointer)
        broker_path = self.checked(next(p for p in self.producers if Path(p['path']).name == 'eval_tool_broker.py'))
        # Read only the literal of a known, completely hashed source file.
        assignments = [node.value for node in ast.parse(broker_path.read_text()).body
                       if isinstance(node, ast.Assign) and any(isinstance(t,ast.Name) and t.id=='BASE_INSTRUCTIONS'
                                                               for t in node.targets)]
        require(len(assignments) == 1, 'known broker instruction literal is missing')
        self.base_instructions = ast.literal_eval(assignments[0])
        require(isinstance(self.base_instructions,str), 'broker instruction literal is not text')
        packet_path = self.checked(next(p for p in self.producers if Path(p['path']).name == 'review_packet.py'))
        assignments = [node.value for node in ast.parse(packet_path.read_text()).body
                       if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='REVIEW_INSTRUCTIONS'
                                                               for t in node.targets)]
        require(len(assignments) == 1, 'known packet instruction literal is missing')
        self.packet_instructions = ast.literal_eval(assignments[0])
        require(isinstance(self.packet_instructions,str) and self.packet_instructions,
                'packet instruction literal is not text')
        self.review_path = root/'worker/root/work/candidate_review.json'
        self.review_ref = review_ref
        self.review = json.loads(self.checked({'path':str(self.review_path),'sha256':review_ref}).read_text())
        workspace = root/'worker/root/work'
        self.workspace = self.temporary/'worker/root/work'
        for role in ('baseline', 'candidate'):
            inventory = self.review[role+'_inventory']
            require(read(reader,self.anchor['source_hashes'][role])['files'] == inventory,
                    'review source inventory differs from original frozen sources')
            self.tree(workspace/role, inventory, self.workspace/role, require_frozen=True)
        plan_ref = self.review['plan_sha256']
        require(self.frozen[str(workspace/'candidate_plan.json')] == plan_ref, 'candidate plan was not frozen')
        self.copy(workspace/'candidate_plan.json', plan_ref, self.workspace/'candidate_plan.json')
        self.copy(self.review_path, review_ref, self.workspace/'candidate_review.json')
        worker_pointer = self.review['worker_receipt_ref']; worker_path = _path(worker_pointer['path'])
        require(worker_path == root/'reviewer/worker.json', 'reviewer receipt is outside its registered trial')
        worker = json.loads(self.checked(worker_pointer).read_text())
        require(worker['qualification_ref'] == self.qualification_ref, 'review used another qualification')
        self.copy(worker_path, worker_pointer['sha256'], self.temporary/'reviewer/worker.json')
        # The producer records the immutable anonymous input, not its namespace
        # mount. Rebuild that identical roster in a fresh verifier-only workspace.
        require(self.review['prompt_ref']['path'] == str(root/'review-input/prompt.txt'),
                'review prompt is outside its registered anonymous input')
        self.tree(root/'review-input', self.review['input_inventory'], self.temporary/'reviewer/root/work')
        for key, frozen_key in [('contract_ref','review_contract'),('checklist_ref','review_checklist'),
                                ('boundaries_ref','review_boundaries')]:
            require(self.review[key]['sha256'] == self.plan['review_inputs'][frozen_key]['sha256'],
                    'review contract changed from the prelaunch plan')
            self.checked(self.plan['review_inputs'][frozen_key])

    def checked(self, pointer):
        require(isinstance(pointer,dict) and set(pointer)=={'path','sha256'}, 'invalid retained pointer')
        logical = str(_path(pointer['path'])); entry = self.files[logical]
        require(entry['sha256'] == pointer['sha256'], 'retained pointer disagrees with the trusted archive inventory')
        path = Path(self.reader.verify_artifact(pointer['sha256']))
        require(path.is_file() and not path.is_symlink() and file_hash(path) == pointer['sha256']
                and path.stat().st_size == entry['bytes'], 'retained artifact bytes changed')
        return self.materialized.get(logical, path)

    def pointer(self, path):
        original = self.original[str(Path(path))]
        ref = self.files[original]['sha256']
        require(file_hash(Path(path)) == ref, 'temporary review input changed')
        return {'path':original,'sha256':ref}

    def copy(self, original, reference, target):
        original = str(original); source = self.checked({'path':original,'sha256':reference})
        require(target.is_relative_to(self.temporary), 'temporary source reconstruction escaped its owned directory')
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with target.open('xb') as stream:
            stream.write(source.read_bytes())
        require(file_hash(target) == reference, 'temporary source reconstruction changed bytes')
        self.materialized[original], self.original[str(target)] = target, original

    def tree(self, root, expected, target, *, require_frozen=False):
        actual = {str(Path(path).relative_to(root)):entry['sha256'] for path,entry in self.files.items()
                  if Path(path).is_relative_to(root)}
        require(actual == expected and expected, 'retained source/view roster is incomplete or contains extra files')
        for name, reference in expected.items():
            relative = Path(name)
            require(not relative.is_absolute() and relative.as_posix()==name and '..' not in relative.parts
                    and '\0' not in name, 'unsafe retained source name')
            original = root/relative
            if require_frozen:
                require(self.frozen[str(original)] == reference, 'source was not frozen before launch')
            self.copy(original,reference,target/relative)

    def restore_packet(self, packet):
        # Exact producer tuples above authorize this literal-only compatibility.
        # Sources, views and packing come from the strict current builder, never
        # from the retained prompt or executable archived Python.
        from review_packet import REVIEW_INSTRUCTIONS
        expected = self.producers[PRODUCER_ORDER.index('review_packet.py')]['sha256']
        require(self.review['review_packet_binding']['producer_sha256'] == expected,
                'review packet names an unknown executed producer')
        require(packet['prompt'].startswith(REVIEW_INSTRUCTIONS + '\n\nThe following attachments'),
                'current packet instruction boundary changed')
        prompt = self.packet_instructions + packet['prompt'][len(REVIEW_INSTRUCTIONS):]
        encoded = prompt.encode('utf-8')
        binding = dict(packet['binding'], producer_sha256=expected,
                       packet_sha256='sha256:' + hashlib.sha256(encoded).hexdigest(), packet_bytes=len(encoded))
        return {'prompt':prompt, 'binding':binding}

    def check_qualification(self, reference, receipt):
        require(reference == self.qualification_ref
                and receipt == json.loads(self.checked(self.qualification_ref).read_text()),
                'retained qualification substituted its anchored receipt')


def replay_retained_source_review(reader, *, anchor_ref, source_review_ref, archive_inventory_ref,
                                 producer_snapshot_ref):
    """The four refs are trusted caller inputs, not fields selected by the review."""
    from eval_candidate_evidence import verify_blind_source_review
    with tempfile.TemporaryDirectory(prefix='aprof-retained-review-') as temporary:
        retained = _RetainedReview(reader,anchor_ref=anchor_ref,review_ref=source_review_ref,
            archive_ref=archive_inventory_ref,producer_snapshot_ref=producer_snapshot_ref,temporary=temporary)
        result = verify_blind_source_review(retained.workspace, retained.plan['release'],
            model=retained.plan['model'], retained=retained)
        require(result['source_review_ref'] == {'path':str(retained.review_path),'sha256':source_review_ref},
                'retained replay rewrote the original review identity')
        return {**result, 'authority':'retained_independent_source_review', 'anchor_ref':anchor_ref,
            'archive_inventory_ref':archive_inventory_ref,'producer_snapshot_ref':producer_snapshot_ref,
            'executed_producers':retained.producers,'qualification_ref':retained.qualification_ref,
            'binary_identity':retained.binary,'binary_bytes_replayed':False,
            'admission_authority':False,'eligible_for_publication':False}
