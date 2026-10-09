#!/usr/bin/env python3
"""Run prebuilt host-only sizeof probes and collect planner metadata. No builds.

--compiler-sha256 is an explicit prior toolchain fingerprint, avoiding repeated
large compiler hashing. Caller must verify it belongs to --compiler. The exact
probe compile command is checked against that compiler and saved with output.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess


def file_evidence(path):
    path = Path(path)
    return {'path': str(path.resolve()),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def compile_command(build_dir, target):
    """Read export or derive one direct ASC recipe; never execute make text."""
    source = Path(target['source']).resolve()
    database = build_dir / 'compile_commands.json'
    if database.exists():
        commands = json.loads(database.read_text())
        matching = [c for c in commands if
                    (Path(c.get('directory', build_dir)) / c['file']).resolve() == source]
        if len(matching) != 1:
            raise ValueError(f'exactly one compile command required: {source}')
        row = matching[0]
        command = row.get('arguments') or shlex.split(row['command'])
        return command, {'kind': 'cmake_compile_commands_export',
                         'evidence': [file_evidence(database)],
                         'working_directory': str(Path(row.get('directory', build_dir)).resolve())}
    target_dir = build_dir / 'CMakeFiles' / (target['target'] + '.dir')
    build_make, flags_make = target_dir / 'build.make', target_dir / 'flags.make'
    variables = {}
    for name in ('ASC_DEFINES', 'ASC_INCLUDES', 'ASC_FLAGS'):
        values = re.findall(r'^' + name + r' =([^\n]*)$', flags_make.read_text(), re.M)
        if len(values) != 1 or '$' in values[0] or '\\' in values[0]:
            raise ValueError(f'unsupported Make variable definition: {name}')
        variables[name] = values[0].strip()
    matches = []
    for line in build_make.read_text().splitlines():
        if not line.startswith('\t') or ' -c ' not in line:
            continue
        expanded = line.strip()
        for name, value in variables.items():
            expanded = expanded.replace('$(' + name + ')', value)
        if '$' in expanded or any(x in expanded for x in (';', '&&', '|', '`')):
            raise ValueError('unsupported Make recipe expansion or shell composition')
        argv = shlex.split(expanded)
        if str(source) in argv:
            matches.append((argv, line.strip()))
    if len(matches) != 1:
        raise ValueError(f'exactly one direct ASC Make recipe required: {source}')
    command, recipe = matches[0]
    return command, {'kind': 'derived_from_cmake_makefiles',
                     'not_a_compile_commands_export': True,
                     'derivation': 'literal ASC_DEFINES/ASC_INCLUDES/ASC_FLAGS substitution; shlex tokenization',
                     'recipe': recipe, 'variables': variables,
                     'working_directory': str(build_dir.resolve()),
                     'evidence': [file_evidence(build_make), file_evidence(flags_make)]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--probe-dir', type=Path, required=True)
    p.add_argument('--build-dir', type=Path, required=True)
    p.add_argument('--compiler', type=Path, required=True)
    p.add_argument('--compiler-sha256', required=True)
    p.add_argument('--cmake-parameters-json', required=True,
                   help='JSON array of actual configure arguments')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if not re.fullmatch('[0-9a-f]{64}', a.compiler_sha256):
        p.error('compiler SHA256 must be a prior verified fingerprint')
    params = json.loads(a.cmake_parameters_json)
    if not isinstance(params, list) or not params:
        p.error('actual CMake parameters array required')
    if a.output.exists():
        p.error('refuse overwrite existing metadata')
    manifest = json.loads((a.probe_dir / 'probe_manifest.json').read_text())
    compiler = a.compiler.resolve(strict=True)
    version = subprocess.run([str(compiler), '--version'], capture_output=True,
                             text=True, check=True).stdout.strip()
    evidence_dir = a.output.parent / (a.output.stem + '-evidence')
    evidence_dir.mkdir(parents=True, exist_ok=False)
    entries = {}
    for target in manifest['targets']:
        command, command_provenance = compile_command(a.build_dir, target)
        if Path(command[0]).resolve() != compiler:
            raise ValueError('probe compile compiler differs from provided compiler')
        if '--npu-arch=dav-2201' not in command:
            raise ValueError('missing expected architecture compile argument')
        cmake_source = a.probe_dir / 'CMakeLists.txt'
        standard = re.findall(r'set\(CMAKE_CXX_STANDARD\s+(\d+)\)', cmake_source.read_text()) if cmake_source.exists() else []
        dialect = {'cmake_cxx_standard_declared': standard[0] if len(standard) == 1 else None,
                   'asc_std_arguments': [x for x in command if x.startswith('-std=')],
                   'asc_default_dialect': 'unknown_not_probed',
                   'declaration_does_not_prove_ASC_dialect': True}
        if cmake_source.exists():
            dialect['cmake_source_evidence'] = file_evidence(cmake_source)
        result = subprocess.run([str((a.build_dir / target['target']).resolve())],
                                capture_output=True, text=True, check=True)
        observed = json.loads(result.stdout)
        for key in ('adapter_sha256', 'header_sha256', 'kernel_sha256', 'source_sha256', 'type'):
            if observed.get(key) != target[key]:
                raise ValueError(f'probe identity mismatch: {key}')
        for key in ('bytes', 'alignof', 'size_t_bytes'):
            if type(observed.get(key)) is not int or observed[key] <= 0:
                raise ValueError(f'invalid probe measurement: {key}')
        evidence = evidence_dir / (target['target'] + '.json')
        evidence.write_text(result.stdout)
        entry = {**observed, 'compiler_command': command,
                 'compiler_command_provenance': command_provenance,
                 'language_dialect': dialect,
                 'compiler_sha256': a.compiler_sha256, 'compiler_version': version,
                 'cmake_parameters': params, 'evidence_path': str(evidence.resolve()),
                 'evidence_sha256': hashlib.sha256(evidence.read_bytes()).hexdigest()}
        old = entries.get(observed['adapter_sha256'])
        if old and any(old[k] != observed[k] for k in observed):
            raise ValueError('duplicate adapter probes disagree')
        entries.setdefault(observed['adapter_sha256'], entry)
    a.output.write_text(json.dumps({'entries': list(entries.values())}, indent=2) + '\n')
    print(json.dumps({'output': str(a.output.resolve()), 'unique_adapters': len(entries),
                      'probes_run': len(manifest['targets'])}))


if __name__ == '__main__':
    main()
