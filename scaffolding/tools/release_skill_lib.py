#!/usr/bin/env python3
"""Seal a new version directory, or verify an existing immutable release."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tomllib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'collection/scripts'))
from aprof_layout import release_module


def publication_evidence(root, validation_run, measurement_validation=None, *,
                         scoped_publication=None, scope_amendment_sha256=None):
    """Replay the version's independent qualification before writing stable bytes."""
    root = Path(root).resolve()
    if scoped_publication is not None or scope_amendment_sha256 is not None:
        if (root.parent.name != 'graph-base' or root.name != '1.0.0'
                or scoped_publication is None or scope_amendment_sha256 is None
                or validation_run is not None or measurement_validation is not None):
            raise ValueError('scoped publication requires only the 1.0.0 report and explicit amendment hash')
        from verify_exp_scoped_publication import verify_exp_scoped_publication
        qualification = verify_exp_scoped_publication(root, Path(scoped_publication).resolve(),
            amendment_sha256=scope_amendment_sha256)
        if (qualification.get('accepted') is not True
                or qualification.get('scope') != 'exp_only_910c_a3_cann900'
                or qualification.get('amendment_ref') != scope_amendment_sha256):
            raise ValueError('exp-only publication lacks the independently replayed authorized scope')
        return {'exp_scoped_publication': qualification}
    if root.parent.name == 'graph-base' and root.name == '0.5.1':
        if measurement_validation is None:
            raise ValueError('graph-base/0.5.1 seal requires --measurement-validation with independent method acceptance')
        if validation_run is not None:
            raise ValueError('graph-base/0.5.1 uses --measurement-validation, not the Teacher evaluation argument')
        from verify_task_window_publication import verify_task_window_publication
        qualification = verify_task_window_publication(root, Path(measurement_validation).resolve())
        if qualification.get('accepted') is not True:
            raise ValueError('graph-base/0.5.1 measurement method lacks independent publication acceptance')
        return {'measurement_method': qualification}
    if root.parent.name != 'graph-base' or root.name != '1.0.0':
        return None
    if measurement_validation is not None:
        raise ValueError('graph-base/1.0.0 requires Teacher and equal-budget acceptance via --validation-run')
    if validation_run is None:
        raise ValueError('graph-base/1.0.0 seal requires --validation-run with the frozen 45-run acceptance')
    repo = Path(__file__).resolve().parents[2]
    from verify_teacher_wiki import verify
    audit = repo / 'scaffolding/curation/graph-base-1.0.0.json'
    teacher = verify(repo, repo.parent / 'optimization-traces', root, audit)
    if teacher['promoted_skills'] < 1:
        raise ValueError('graph-base/1.0.0 has no independently validated skill promotion')
    from evaluate_skill_release import verify_publication
    evaluation = verify_publication(Path(validation_run).resolve(), release=root)
    if evaluation.get('accepted') is not True:
        raise ValueError('graph-base/1.0.0 equal-budget results do not support stable publication')
    return {'teacher': teacher, 'teacher_audit_sha256': release_module(root).sha(audit),
            'equal_budget_evaluation': evaluation}


def seal(root, source_commit, source_version, validation_run=None, measurement_validation=None, *,
         scoped_publication=None, scope_amendment_sha256=None):
    root = Path(root).resolve()
    target = root / 'release.json'
    if target.exists():
        raise ValueError('release already sealed; create a new version directory')
    tool = release_module(root)
    errors = tool.registry_errors(root)
    if errors:
        raise ValueError('; '.join(errors))
    registry = json.loads((root / 'skillgraph/registry.json').read_text())
    version = registry['library']['version']
    if root.name != version:
        raise ValueError('version directory and registry differ')
    candidate_files = tool.inventory(root)
    qualification = publication_evidence(root, validation_run, measurement_validation,
        scoped_publication=scoped_publication, scope_amendment_sha256=scope_amendment_sha256)
    runtime = tomllib.loads((root / 'runtime/pyproject.toml').read_text())['project']['version']
    graphs = {}
    for path in sorted((root / 'skillgraph/versions').iterdir()):
        if not path.is_dir():
            continue
        subprocess.run([str(root / 'tools/aprofctl'), 'graph', 'validate', '--graph', str(path)], check=True,
                       stdout=subprocess.DEVNULL)
        graphs[path.name] = tool.sha(path / 'graph.json')
    files = tool.inventory(root)
    if qualification is not None and files != candidate_files:
        raise ValueError('candidate changed while verifying publication evidence')
    value = {'schema_version': 1, 'status': 'stable', 'release_id': f'{root.parent.name}/{version}',
             'skill_version': version, 'runtime_version': runtime, 'default_graph': 'v0002',
             'source_commit': source_commit, 'source_skill_version': source_version,
             'graphs': graphs, 'files': files}
    if qualification is not None:
        value['publication_evidence'] = qualification
        provenance = qualification.get('measurement_method', {}).get('source_provenance')
        if provenance is not None:
            if not provenance['source_commit'].startswith(source_commit):
                raise ValueError('source commit differs from independently verified worktree provenance')
            value['source_provenance'] = provenance
    with target.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('seal', 'check'))
    parser.add_argument('--skill-lib', required=True, type=Path)
    parser.add_argument('--source-commit')
    parser.add_argument('--source-version')
    parser.add_argument('--validation-run', type=Path,
                        help='frozen 45-run equal-budget acceptance required for graph-base/1.0.0')
    parser.add_argument('--measurement-validation', type=Path,
                        help='independent measurement-method acceptance required for graph-base/0.5.1')
    parser.add_argument('--scoped-publication', type=Path,
                        help='exp-only continuation publication report; requires an authorized amendment hash')
    parser.add_argument('--scope-amendment-sha256',
                        help='explicit caller-trusted SHA256 of the exp-only scope amendment')
    args = parser.parse_args()
    if args.command == 'seal':
        if not args.source_commit or not args.source_version:
            parser.error('seal requires --source-commit and --source-version')
        value = seal(args.skill_lib, args.source_commit, args.source_version, args.validation_run, args.measurement_validation,
                     scoped_publication=args.scoped_publication, scope_amendment_sha256=args.scope_amendment_sha256)
    else:
        value = release_module(args.skill_lib).verify(args.skill_lib)
    print(json.dumps({'valid': True, 'release_id': value['release_id'], 'files': len(value['files'])}))


if __name__ == '__main__':
    main()
