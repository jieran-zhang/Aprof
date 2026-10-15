"""Post-task trace-collection supplement for the existing mechanical source proof.

No new source identity is invented: every path/hash must already occur in the
original proof or build/report references. No profiling data is copied here.
"""
from pathlib import Path

from timing_admission import checked_path, read, require


def required_source_files(proof, build, report):
    assembly = Path(build['binary']['path']).parent.parent
    files = {}
    def add(path, reference):
        path = Path(path)
        require(path.is_absolute() and '..' not in path.parts and '\0' not in str(path), 'unsafe original source path')
        name = str(path)
        require(name not in files or files[name] == reference, 'conflicting original source hashes')
        files[name] = reference
    for path, reference in proof['producer_files'].items(): add(path, reference)
    add(assembly / 'source-review.json', report['source_review_ref'])
    add(build['attempt_ref']['path'], build['attempt_ref']['sha256'])
    for root, inventory in [(assembly / 'source', proof['adapted_files']),
            *((Path(proof['roles'][role]['path']), proof['roles'][role]['files']) for role in ('baseline', 'candidate'))]:
        for name, reference in inventory.items():
            relative = Path(name)
            require(not relative.is_absolute() and relative.as_posix() == name and '\0' not in name
                    and not {'.', '..'}.intersection(relative.parts), 'unsafe source-relative name')
            add(root / relative, reference)
    historical = proof['historical_source_binding']
    for binding in [historical['freeze'], *historical['roles'].values()]: add(binding['path'], binding['sha256'])
    return dict(sorted(files.items()))


def archive_task_rule_sources(local_reader, report_ref, archive_store):
    """Called by trace collection before deleting task-local sources, after exit."""
    report = read(local_reader, report_ref)
    proof, build = (read(local_reader, report[key]) for key in ('source_review_ref', 'build_receipt_ref'))
    files = required_source_files(proof, build, report)
    for path, reference in files.items():
        # Small source files may not have been indexed if the task ended before
        # Task collection. Their expected hashes still come from the old proof.
        actual = Path(path)
        require(actual.is_file() and not any(p.is_symlink() for p in (actual, *actual.parents)),
                'original source is absent or symlinked before trace collection')
        from aprof_runtime.jsonio import file_hash
        require(file_hash(actual) == reference, 'source changed before post-task collection')
        require(archive_store.register_artifact(actual) == reference, 'source changed during post-task collection')
    for reference in files.values(): archive_store.verify_artifact(reference)
    value = {'schema_version': 1, 'kind': 'task_rule_source_archive', 'owner': 'trace_collection',
             'cost_scope': 'post_task', 'source_review_ref': report['source_review_ref'], 'files': files}
    from aprof_runtime.traces import register_json_artifact
    return register_json_artifact(archive_store, value)


def verify_source_archive(reader, reference, proof, build, report):
    archive = read(reader, reference)
    require(set(archive) == {'schema_version', 'kind', 'owner', 'cost_scope', 'source_review_ref', 'files'}
            and archive['schema_version'] == 1 and archive['kind'] == 'task_rule_source_archive'
            and archive['owner'] == 'trace_collection' and archive['cost_scope'] == 'post_task'
            and archive['source_review_ref'] == report['source_review_ref']
            and archive['files'] == required_source_files(proof, build, report),
            'source archive differs from the original mechanical proof')
    return {path: checked_path(reader, path, digest) for path, digest in archive['files'].items()}
