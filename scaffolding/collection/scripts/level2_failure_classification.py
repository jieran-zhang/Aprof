#!/usr/bin/env python3
"""Read-only, positive-evidence attribution of a terminal source attempt.

Unknown failures remain infrastructure_blocked. Exception names and nonzero exit
codes never establish source failure by themselves. The returned file hashes must
be frozen in feedback and replayed by the finalizer. Callers retain every actual
execution/cost record and do not close feedback for infrastructure_blocked.

This deliberately recognizes a small set of proofs; unsupported diagnostics,
crashes, missing outputs and arbitrary guard-script failures require investigation.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import re
import tarfile

VERSION = 'level2_failure_classification_v1'
INFRA_TYPES = {'TimeoutExpired', 'TimeoutError', 'KeyboardInterrupt', 'OSError',
    'FileNotFoundError', 'PermissionError', 'ConnectionError', 'BrokenPipeError',
    'BlockingIOError', 'InterruptedError', 'IsADirectoryError', 'NotADirectoryError',
    'ProcessLookupError', 'ChildProcessError', 'MemoryError', 'EOFError'}
# Restrict compiler admission to semantic diagnostics at an original source file.
# Missing headers/libraries, tool crashes and resource errors are never admitted.
SEMANTIC_DIAGNOSTIC = re.compile(r'^(?:use of undeclared identifier\b|undeclared identifier\b|'
    r'no matching (?:function|member function|constructor)\b|no member named\b|'
    r'expected (?:expression|identifier|unqualified-id|type|parameter)\b|'
    r'invalid operands to binary expression\b|cannot initialize\b|'
    r'incompatible (?:pointer|integer|function)\b|redefinition of\b|'
    r'too (?:few|many) arguments\b)')
INFRA_LOG = re.compile(r'no such file|file not found|command not found|permission denied|'
    r'no space left|disk quota|cannot execute|cannot find -l|unable to (?:execute|load)|'
    r'error while loading|internal compiler error|segmentation fault|killed signal|'
    r'out of memory|\btimed? ?out\b|\bterminated\b', re.I)
KERNEL_TYPE_DIAGNOSTIC = re.compile(
    r'^ld\.lld: error: Error: the type of kernel function '
    r'(sc_([AB])_([0-9a-f]{12})_([A-Za-z_][A-Za-z_0-9]*)) '
    r'auto derivate failed, please manually add the function type attribute$')


def reviewed_role_makefile(build, role, operator, compiler):
    """Exact effective statements of the supported CMake 3.22 ASC role recipe.

    This is deliberately a finite allowlist, not a GNU Make interpreter. Other
    generator layouts need their own review before positive failure attribution.
    """
    return r'''.DELETE_ON_ERROR:
.SUFFIXES:
% : %,v
% : RCS/%
% : RCS/%,v
% : SCCS/s.%
% : s.%
.SUFFIXES: .hpux_make_needs_suffix_list
$(VERBOSE)MAKESILENT = -s
$(VERBOSE).SILENT:
cmake_force:
.PHONY : cmake_force
SHELL = /bin/sh
CMAKE_COMMAND = /usr/bin/cmake
RM = /usr/bin/cmake -E rm -f
EQUALS = =
CMAKE_SOURCE_DIR = {build}
CMAKE_BINARY_DIR = {build}/build
include CMakeFiles/role_{role}.dir/depend.make
include CMakeFiles/role_{role}.dir/compiler_depend.make
include CMakeFiles/role_{role}.dir/progress.make
include CMakeFiles/role_{role}.dir/flags.make
CMakeFiles/role_{role}.dir/{role}/op_host/{operator}.asc.o: CMakeFiles/role_{role}.dir/flags.make
CMakeFiles/role_{role}.dir/{role}/op_host/{operator}.asc.o: ../{role}/op_host/{operator}.asc
CMakeFiles/role_{role}.dir/{role}/op_host/{operator}.asc.o: CMakeFiles/role_{role}.dir/compiler_depend.ts
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green --progress-dir={build}/build/CMakeFiles --progress-num=$(CMAKE_PROGRESS_1) "Building ASC object CMakeFiles/role_{role}.dir/{role}/op_host/{operator}.asc.o"
	{compiler} $(ASC_DEFINES) $(ASC_INCLUDES) -fPIC  $(ASC_FLAGS) -MD -MT CMakeFiles/role_{role}.dir/{role}/op_host/{operator}.asc.o -MF CMakeFiles/role_{role}.dir/{role}/op_host/{operator}.asc.o.d -o CMakeFiles/role_{role}.dir/{role}/op_host/{operator}.asc.o -c --asc-aicore-lang {build}/{role}/op_host/{operator}.asc
role_{role}_OBJECTS = \
"CMakeFiles/role_{role}.dir/{role}/op_host/{operator}.asc.o"
role_{role}_EXTERNAL_OBJECTS =
librole_{role}.so: CMakeFiles/role_{role}.dir/{role}/op_host/{operator}.asc.o
librole_{role}.so: CMakeFiles/role_{role}.dir/build.make
librole_{role}.so: CMakeFiles/role_{role}.dir/link.txt
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green --bold --progress-dir={build}/build/CMakeFiles --progress-num=$(CMAKE_PROGRESS_2) "Linking ASC shared library librole_{role}.so"
	$(CMAKE_COMMAND) -E cmake_link_script CMakeFiles/role_{role}.dir/link.txt --verbose=$(VERBOSE)
CMakeFiles/role_{role}.dir/build: librole_{role}.so
.PHONY : CMakeFiles/role_{role}.dir/build
CMakeFiles/role_{role}.dir/clean:
	$(CMAKE_COMMAND) -P CMakeFiles/role_{role}.dir/cmake_clean.cmake
.PHONY : CMakeFiles/role_{role}.dir/clean
CMakeFiles/role_{role}.dir/depend:
	cd {build}/build && $(CMAKE_COMMAND) -E cmake_depends "Unix Makefiles" {build} {build} {build}/build {build}/build {build}/build/CMakeFiles/role_{role}.dir/DependInfo.cmake --color=$(COLOR)
.PHONY : CMakeFiles/role_{role}.dir/depend'''.format(build=build, role=role, operator=operator, compiler=compiler)


def effective_make_lines(text):
    lines = []
    continued = False
    for line in text.splitlines():
        ignored = not line.strip() or line.lstrip().startswith('#')
        require(not (continued and ignored), 'comment/blank inside a Make continuation is unsupported')
        require(not (line.lstrip().startswith('#') and line.rstrip().endswith('\\')),
                'continued Make comments can hide effective statements')
        continued = line.rstrip().endswith('\\')
        if not ignored:
            lines.append(line.rstrip())
    require(not continued, 'incomplete Make continuation')
    return lines


class Unproven(ValueError):
    pass


def require(value, reason):
    if not value:
        raise Unproven(reason)


def canonical_path(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts, 'noncanonical evidence path is unsupported')
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'symlink evidence is unsupported')
    require(path == path.resolve(), 'noncanonical evidence path is unsupported')
    return path


class Evidence:
    def __init__(self):
        self.refs = {}

    def path(self, path):
        path = canonical_path(path)
        require(path.is_file(), 'missing evidence: ' + str(path))
        return path

    def read(self, path, *, text=False):
        path = self.path(path)
        raw = path.read_bytes()
        self.refs[str(path)] = {'path': str(path), 'sha256': 'sha256:' + hashlib.sha256(raw).hexdigest()}
        return raw.decode() if text else json.loads(raw)

    def file(self, path):
        path = self.path(path)
        h = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
                h.update(block)
        ref = {'path': str(path), 'sha256': 'sha256:' + h.hexdigest()}
        self.refs[str(path)] = ref
        return ref

    def bound(self, ref, expected=None, *, text=False, binary=False):
        require(isinstance(ref, dict) and set(ref) >= {'path', 'sha256'}, 'missing evidence pointer')
        path = self.path(ref['path'])
        if expected is not None:
            require(path == Path(expected).absolute(), 'evidence points outside expected location')
        actual = self.file(path)
        require(actual['sha256'] == ref['sha256'], 'evidence hash differs: ' + str(path))
        return actual if binary else self.read(path, text=text)


def infra_error(error):
    return isinstance(error, dict) and error.get('type') in INFRA_TYPES


def process(row, exit_code=0):
    code = row.get('exit_status', row.get('exit_code'))
    require(type(code) is int and code == exit_code, 'process exit does not establish the required outcome')
    require(row.get('finished_at', row.get('ended_at')) is not None and row.get('started_at') is not None,
            'process completion is not recorded')
    require(not row.get('timed_out') and not infra_error(row.get('error')), 'process timed out or failed infrastructure')
    if exit_code == 0:
        require(not row.get('error') and row.get('status', 'passed') == 'passed', 'process did not complete successfully')


def health(e, root):
    for name in ('health-before.json', 'health-after.json'):
        row = e.read(root / name)
        require(row.get('status') == 'passed' and not row.get('error')
                and row.get('exit_status', row.get('exit_code')) == 0,
                'healthy before/after records are required')


def stage_location(e, parent, stage):
    sid = stage.get('stage_id', '')
    prefix = parent.name + '-'
    require(sid.startswith(prefix) and re.fullmatch(r'[A-Za-z0-9_-]+', sid[len(prefix):]),
            'stage does not identify this candidate')
    directory = parent / 'stages' / sid[len(prefix):]
    require(e.read(directory / 'result.json') == stage, 'stage result differs from recorded evidence')
    require(stage.get('candidate_id') == parent.name, 'stage candidate differs')
    return directory


def reviewed_original_role_build(e, parent, stage, configure, execution):
    """Replay frozen original source, both exact adapters and retained ASC recipes."""
    build = parent / 'build'
    config_out = e.read(build / 'configure-execution/stdout.log', text=True)
    config_err = e.read(build / 'configure-execution/stderr.log', text=True)
    require(not config_err.strip() and not INFRA_LOG.search(config_out), 'configuration tool/environment failure')
    compiler_paths = re.findall(r'^-- CMAKE_ASC_COMPILER: (/[^\n]+/bisheng)$', config_out, re.M)
    linker_paths = re.findall(r'^-- CMAKE_ASC_LLD_LINKER: (/[^\n]+/ld\.lld)$', config_out, re.M)
    require(len(compiler_paths) == len(linker_paths) == 1, 'configured ASC compiler/linker identity is absent')
    compiler = Path(compiler_paths[0]); sdk = compiler.parent.parent
    require('..' not in compiler.parts and linker_paths[0].startswith(str(sdk) + '/'), 'compiler/linker SDK identity differs')
    require(configure.get('environment_overrides') == execution.get('environment_overrides') == {},
            'unreviewed build environment override')
    setup = ('source ' + str(sdk / 'set_env.sh') + ' || exit $?; '
             'export LD_LIBRARY_PATH=/usr/local/Ascend/driver/lib64/common:'
             '/usr/local/Ascend/driver/lib64/driver:${LD_LIBRARY_PATH:-}; exec "$@"')
    for record in (configure, execution):
        shell = record.get('shell_argv', [])
        require(isinstance(shell, list) and len(shell) == len(record['argv']) + 7
                and shell[:2] == ['taskset', '-c'] and re.fullmatch(r'[0-9,-]+', shell[2])
                and shell[3:7] == ['bash', '-c', setup, 'feedback-hardware']
                and shell[7:] == record['argv'], 'executed SDK environment differs from configured compiler')
    compiler_records = list((build / 'build/CMakeFiles').glob('*/CMakeASCCompiler.cmake'))
    require(len(compiler_records) == 1, 'one recorded ASC compiler configuration is required')
    compiler_record = e.read(compiler_records[0], text=True)
    require(re.findall(r'^set\(CMAKE_ASC_COMPILER "([^"]+)"\)$', compiler_record, re.M) == compiler_paths
            and 'set(CMAKE_ASC_COMPILER_LOADED 1)' in compiler_record, 'recorded ASC compiler differs')

    # The stage's original archive, not a generated adapter, is source authority.
    plan = e.read(parent / 'stages' / stage['stage_id'][len(parent.name) + 1:] / 'stage-plan.json')
    archive = parent / 'source.tar'
    require(e.file(archive)['sha256'] == plan.get('source_hash'), 'frozen source archive differs from stage')
    native = {}
    with tarfile.open(archive) as stream:
        names = set()
        for member in stream.getmembers():
            path = Path(member.name)
            require(not path.is_absolute() and '..' not in path.parts and member.name not in names
                    and (member.isfile() or member.isdir()), 'unsafe or duplicate frozen source member')
            names.add(member.name)
            parts = path.parts[1:] if path.parts and path.parts[0] == 'source' else path.parts
            if member.isfile() and parts and parts[0] in ('op_host', 'op_kernel'):
                relative = Path(*parts)
                require(str(relative) not in native, 'duplicate normalized frozen source member')
                data = stream.extractfile(member).read()
                source = parent / 'op' / relative
                e.file(source)
                require(source.read_bytes() == data, 'original source differs from frozen archive')
                native[str(relative)] = data
    actual = {str(p.relative_to(parent / 'op')) for name in ('op_host', 'op_kernel')
              for p in (parent / 'op' / name).rglob('*') if p.is_file()}
    require(native and actual == set(native), 'original native source set differs from archive')
    native_hash = hashlib.sha256()
    for name, data in sorted(native.items()):
        native_hash.update(name.encode() + b'\0' + data + b'\0')
    source_hash = native_hash.hexdigest()
    manifest = e.read(build / 'build_manifest.json')
    require(manifest.get('version') == 'shared_context_build_v1' and set(manifest.get('roles', {})) == {'A', 'B'},
            'role source manifest is absent')
    # Replay the reviewed adapter, rather than attempting to infer preprocessor
    # meaning from an include that may be disabled or shadowed by generated code.
    import shared_context_build
    import level2_adapters
    require(manifest.get('operator') == parent.parent.parent.name
            and manifest['operator'] in shared_context_build.LEVEL2_OPERATORS,
            'kernel-type manifest operator is not this reviewed Level2 task')
    e.file(Path(shared_context_build.__file__).resolve())
    e.file(Path(level2_adapters.__file__).resolve())
    harness = Path(shared_context_build.HARNESS)
    require(configure.get('cwd') == execution.get('cwd') == str(harness.parents[3]),
            'compiler working directory differs from reviewed harness repository')
    require(manifest.get('harness') == {p.name: e.file(p)['sha256'][7:] for p in harness.iterdir() if p.is_file()},
            'build harness differs from recorded implementation')
    expected_hosts = {}
    for role in ('A', 'B'):
        generated, identity, original = shared_context_build.generate_adapter(parent / 'op', manifest['operator'], role, source_hash)
        require(all(manifest['roles'][role].get(k) == v for k, v in identity.items()), 'regenerated role identity differs')
        expected_hosts[role] = generated
        copied_files = {str(p.relative_to(build / role)) for name in ('op_host', 'op_kernel')
                        for p in (build / role / name).rglob('*') if p.is_file()}
        require(copied_files == set(native), 'copied role source file set differs from frozen original')
        for name, data in native.items():
            path = build / role / name
            e.file(path)
            expected = generated.encode() if name == 'op_host/' + manifest['operator'] + '.asc' else data
            require(path.read_bytes() == expected, 'copied role source differs from replayed original source')
    for role in ('A', 'B'):
        identity = manifest['roles'][role]
        flags = e.read(build / 'build/CMakeFiles' / f'role_{role}.dir/flags.make', text=True)
        recipe = e.read(build / 'build/CMakeFiles' / f'role_{role}.dir/build.make', text=True)
        clean_lines = lambda text: [line for line in text.splitlines() if line.strip() and not line.startswith('#')]
        role_dir = f'CMakeFiles/role_{role}.dir/'
        require(re.findall(r'^include (.+)$', recipe, re.M) == [role_dir + name for name in
                    ('depend.make', 'compiler_depend.make', 'progress.make', 'flags.make')],
                'unreviewed make include changes object command authority')
        for name in ('depend.make', 'compiler_depend.make', 'compiler_depend.ts'):
            require(not clean_lines(e.read(build / 'build' / role_dir / name, text=True)),
                    'nonempty generated make dependencies require review')
        require(clean_lines(e.read(build / 'build' / role_dir / 'progress.make', text=True))
                == [f'CMAKE_PROGRESS_1 = {1 if role == "A" else 3}',
                    f'CMAKE_PROGRESS_2 = {2 if role == "A" else 4}'], 'unreviewed make progress variables')
        require(re.findall(r'^CMAKE_COMMAND\s*[:+?!]?=\s*(.*)$', recipe, re.M) == ['/usr/bin/cmake']
                and re.findall(r'^SHELL\s*[:+?!]?=\s*(.*)$', recipe, re.M) == ['/bin/sh'],
                'unreviewed make command or shell executable')
        assignments = re.findall(r'^(ASC_[A-Z_]+) = (.*)$', flags, re.M)
        expected_flags = {'ASC_DEFINES': f'-Drole_{role}_EXPORTS',
            'ASC_INCLUDES': ' '.join('-I' + str(p) for p in (build / role / 'op_host', build / role / 'op_kernel', harness)),
            'ASC_FLAGS': '--npu-arch=' + identity.get('npu_arch', '')}
        require(f'# compile ASC with {compiler}' in flags and len(assignments) == len(expected_flags)
                and clean_lines(flags) == [key + ' = ' + value for key, value in expected_flags.items()]
                and dict(assignments) == expected_flags
                and effective_make_lines(recipe) == effective_make_lines(
                    reviewed_role_makefile(build, role, manifest['operator'], compiler)),
                'retained role Make variables, targets or commands differ from the reviewed complete recipe')
    return {'build': build, 'sdk': sdk, 'compiler': compiler, 'native': native, 'source_hash': source_hash, 'manifest': manifest, 'expected_hosts': expected_hosts}


def kernel_type_failure(e, parent, stage, configure, execution, stdout, stderr):
    """A narrow linker proof for original, frozen, scalar-only kernel entries.

    CMake's successful configuration alone is not enough. Bind both failed role
    symbols to the same unchanged original definition, the emitted rename and
    source digest, and the recorded ASC compiler/compile recipe. Any extra
    diagnostic, unsupported source syntax, or incomplete proof stays blocked.
    """
    require(execution.get('exit_status') == 2, 'kernel-type proof requires build exit 2')
    matches = [KERNEL_TYPE_DIAGNOSTIC.fullmatch(line) for line in stderr.splitlines()]
    failures = [m for m in matches if m]
    require(failures and {m[2] for m in failures} == {'A', 'B'}, 'both role kernel-type diagnostics are required')
    # Parallel compiler drivers can interleave their harmless failure prefixes.
    for line, match in zip(stderr.splitlines(), matches):
        if match or not line.strip():
            continue
        require(re.fullmatch(r'(?:bisheng|: |error: )*ld\.lld command failed with exit code 1 \(use -v to see invocation\)', line)
                or re.fullmatch(r'gmake(?:\[\d+\])?: \*\*\* (?:\[[^\n]+\] Error [12]|Waiting for unfinished jobs\.{3,4})', line),
                'additional linker/compiler diagnostic prevents kernel-type attribution')
    require(not re.search(r'\b(?:error|fatal)\s*:', stdout, re.I), 'additional stdout compiler error')
    proof = reviewed_original_role_build(e, parent, stage, configure, execution)
    build, native, source_hash, manifest, expected_hosts = (proof[k] for k in ('build', 'native', 'source_hash', 'manifest', 'expected_hosts'))
    by_role = {role: {m[4] for m in failures if m[2] == role} for role in ('A', 'B')}
    require(by_role['A'] == by_role['B'] and all(m[3] == source_hash[:12] for m in failures),
            'failed role symbols do not identify the same original source')
    for kernel in sorted(by_role['A']):
        require(any(re.search(r'\b' + re.escape(kernel) + r'\s*<<<',
                    re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"', ' ', data.decode(), flags=re.S))
                    for name, data in native.items() if name.startswith('op_host/') and name.endswith('.asc')),
                'failed kernel has no frozen original host invocation')
        definitions = []
        for name, data in native.items():
            if not name.startswith('op_kernel/') or not name.endswith('.asc'):
                continue
            # Strings/comments and preprocessor conditionals cannot prove a
            # compiled original definition. Deliberately accept simple syntax.
            code = re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', ' ', data.decode(), flags=re.S)
            found = re.findall(r'\b__global__\s+__aicore__\s+void\s+' + re.escape(kernel) + r'\s*\([^;{}]*\)\s*\{', code)
            if found:
                require(not re.search(r'^\s*#\s*(?:if|ifdef|ifndef|elif|else|endif)\b', code, re.M),
                        'conditional original kernel declaration is unsupported')
                definitions.extend([name] * len(found))
        require(len(definitions) == 1, 'failed symbol lacks one unambiguous original kernel definition')
        for role in ('A', 'B'):
            symbol = f'sc_{role}_{source_hash[:12]}_{kernel}'
            identity = manifest['roles'][role]
            require(identity.get('role') == role and identity.get('source_dir') == str(parent / 'op')
                    and identity.get('source_sha256') == source_hash
                    and symbol in identity.get('kernel_symbols', '').split(','), 'role symbol/source manifest differs')
            host = build / role / 'op_host' / (manifest['operator'] + '.asc')
            host_text = e.read(host, text=True)
            require(host_text == expected_hosts[role]
                    and e.file(host)['sha256'] == 'sha256:' + identity.get('adapter_sha256', '')
                    and re.findall(r'^#define\s+' + re.escape(kernel) + r'\s+([^\s]+)\s*$', host_text, re.M) == [symbol],
                    'failed role symbol is not the recorded original-kernel rename')
            require(not re.search(r'\b__global__\b', host_text)
                    and re.findall(r'^#include "(\.\./op_kernel/[^"\n]+)"\s*$', host_text, re.M).count('../' + definitions[0]) == 1,
                    'generated adapter declares a kernel or does not include its original definition')
            copied = e.read(build / role / definitions[0], text=True)
            require(copied.encode() == native[definitions[0]], 'generated role changed original kernel implementation')
    return 'original_source_kernel_type_inference', 'Retained completed ASC logs and fully replayed source/adapter/Make artifacts consistently attribute both role diagnostics to one original kernel; inherited Make environment and pre-execution recipe hashes were not recorded.'


# Finite reviewed RMS001 witness, not a general tolerance for generated-path errors.
# The log has interleaved A/B lines followed by complete diagnostics for each role.
# Only exact build/SDK prefixes and whitespace are normalized. Unknown shapes stay
# blocked; literal op_host/../ paths are never passed into Evidence/read/resolve.
RMS_ADDS_NATIVE_SHA256 = 'bb2469fd7529049a87a534210a0f0e79547f8ac4e5a9297a2eaff980b067e9b7'
RMS_ADDS_STDERR_SHA256 = 'b944ce7a28e9b1cef90393ee8320611ab289cf0c8a5287a840f2a9406a15e9b4'


def rms_adds_scalar_failure(e, parent, stage, configure, execution, stdout, stderr):
    require(parent.parent.parent.name == 'rms_norm' and execution.get('exit_status') == 2,
            'RMS scalar proof requires the reviewed task and build exit 2')
    require(stage.get('native_started') is False, 'RMS compile proof must precede native execution')
    proof = reviewed_original_role_build(e, parent, stage, configure, execution)
    require(proof['source_hash'] == RMS_ADDS_NATIVE_SHA256,
            'RMS scalar diagnostic source is outside the reviewed finite witness')
    build, sdk = proof['build'], proof['sdk']
    # Two roles must report the unchanged original line, not a generated helper.
    original = proof['native']['op_kernel/rms_norm_kernel.asc'].decode().splitlines()
    require(original[179] == '            AscendC::PipeBarrier<PIPE_V>(); AscendC::Adds(mean, mean, t_->epsilon, paddedRows);',
            'reviewed RMS Adds expression differs')
    for role in ('A', 'B'):
        identity = proof['manifest']['roles'][role]
        require(identity.get('npu_arch') == 'dav-2201' and identity.get('source_dir') == str(parent / 'op')
                and identity.get('adapter_sha256') == hashlib.sha256(proof['expected_hosts'][role].encode()).hexdigest(),
                'RMS role architecture/source/adapter identity differs')
        host = proof['expected_hosts'][role]
        require(host.splitlines()[14] == '#include "../op_kernel/rms_norm_kernel.asc"',
                'RMS diagnostic include line differs from replayed adapter')
        diagnostic = str(build / role) + "/op_host/../op_kernel/rms_norm_kernel.asc:180:45: error: no matching function for call to 'Adds'"
        require(diagnostic in stderr, 'each role needs a complete original-line diagnostic')
    normalized = ' '.join(stderr.replace(str(build), '$BUILD').replace(str(sdk), '$SDK').split())
    require(hashlib.sha256(normalized.encode()).hexdigest() == RMS_ADDS_STDERR_SHA256,
            'RMS diagnostic has extra errors, paths or an unreviewed interleaving')
    require(sorted(stdout.splitlines()) == sorted(
        f'[ 25%] Building ASC object CMakeFiles/role_{role}.dir/{role}/op_host/rms_norm.asc.o' for role in ('A', 'B')),
        'RMS compiler stdout differs from the reviewed two-role build')
    return 'original_source_rms_adds_gm_scalar_conflict', ('Retained completed ASC diagnostics, frozen original RMS source and fully replayed role/Make artifacts consistently attribute both role failures to Adds receiving a __gm__ float scalar against LocalTensor<float>; inherited Make environment and pre-execution recipe hashes were not recorded.')


def compiler_failure(e, parent, stage):
    require(stage.get('error', {}).get('type') == 'RuntimeError', 'compiler failure is not positively identified')
    build = parent / 'build'
    configure = e.read(build / 'configure-execution/execution.json')
    process(configure)
    require(configure.get('argv') == ['cmake', '-S', str(build), '-B', str(build / 'build')],
            'configure argv differs')
    execution = e.read(build / 'build-execution/execution.json')
    require(execution.get('argv') == ['cmake', '--build', str(build / 'build'), '-j2'], 'build argv differs')
    code = execution.get('exit_status')
    require(type(code) is int and code in (1, 2), 'build exit is not a normal compiler failure')
    process(execution, code)
    require(stage['error']['message'] == f'process failed ({code}): cmake'
            and execution.get('error') == stage['error']['message'], 'compiler wrapper error differs')
    stdout, stderr = (e.read(build / ('build-execution/' + f), text=True) for f in ('stdout.log', 'stderr.log'))
    logs = stdout + '\n' + stderr
    require(not INFRA_LOG.search(logs), 'build logs contain an infrastructure/tool failure')
    if parent.parent.parent.name == 'rms_norm' and "no matching function for call to 'Adds'" in stderr:
        return rms_adds_scalar_failure(e, parent, stage, configure, execution, stdout, stderr)
    if any(KERNEL_TYPE_DIAGNOSTIC.fullmatch(line) for line in stderr.splitlines()):
        return kernel_type_failure(e, parent, stage, configure, execution, stdout, stderr)
    for line in logs.splitlines():
        match = re.match(r'^(/[^\n]+?):([0-9]+):([0-9]+): error: (.+)$', line)
        if match is None or not SEMANTIC_DIAGNOSTIC.match(match[4]):
            continue
        path = Path(match[1])
        if not path.is_relative_to(parent / 'op') or path.suffix not in ('.asc', '.h', '.hpp', '.cpp'):
            continue
        lines = e.read(path, text=True).splitlines()
        require(1 <= int(match[2]) <= len(lines), 'diagnostic location exceeds original source')
        return 'original_source_compiler_diagnostic', 'Completed compiler reported a supported semantic error at original candidate source.'
    raise Unproven('no supported original-source compiler diagnostic; generated adapter or unknown errors require investigation')


def verifier_failure(e, task, parent, stage, directory):
    require(stage.get('native_started') is True, 'correctness failed before any confirmed native execution')
    build = e.read(parent / 'build/build_manifest.json')
    # Standalone may succeed before the prepared path fails. Only the failed
    # completion is eligible, never an unrelated earlier oracle result.
    roots = [directory / name for name in ('standalone', 'evidence') if (directory / name / 'completion.json').is_file()]
    failed = [(root, e.read(root / 'completion.json')) for root in roots]
    failed = [(root, row) for root, row in failed if row.get('status') == 'failed']
    require(len(failed) == 1, 'one failed correctness completion is required')
    root, completion = failed[0]
    require(not completion.get('health_error') and completion.get('error') == stage.get('error'),
            'correctness error is not the completed oracle failure')
    health(e, root)
    request = e.read(root / 'request.json')
    oracle = task / 'baseline/scripts/verify_result.py'
    oracle_ref = e.file(oracle)
    if root.name == 'standalone':
        require(request.get('verifier') == oracle_ref, 'standalone request does not bind original oracle')
        require(request.get('standalone') == build.get('standalone'), 'standalone request binary differs')
    else:
        require(request.get('verifier_hash') == oracle_ref['sha256'], 'prepared request does not bind original oracle')
        require(request.get('role_build_hash') == e.file(parent / 'build/build_manifest.json')['sha256'], 'prepared build differs')
    # Exact stdout/result agreement plus original-verifier identity distinguishes
    # a numeric failure from generic ImportError/OSError/RuntimeError in Python.
    for case in sorted(root.glob('case_[0-9][0-9]')):
        verify_path = case / 'verify.execution.json'
        if not verify_path.is_file():
            verify_path = case / 'verify/execution.json'
        if not verify_path.is_file():
            continue
        verify = e.read(verify_path)
        if verify.get('exit_status', verify.get('exit_code')) != 1:
            continue
        process(verify, 1)
        error = verify.get('error')
        require(isinstance(error, dict) and error.get('type') == 'RuntimeError'
                and error.get('message') in ('original oracle main exited 1', 'command exited 1'),
                'verifier exited without a known numeric-result termination')
        require(stage.get('error') == error, 'stage error differs from oracle termination')
        argv = verify.get('argv', [])
        require(str(oracle) in argv and '--metadata' in argv and argv.count('--metadata') == 1,
                'verifier argv does not invoke the original oracle')
        metadata_path = Path(argv[argv.index('--metadata') + 1])
        # Relocated oracle metadata needs its own reviewed proof. Until supported
        # here, keep it unfinished instead of inferring from a similarly named file.
        require(metadata_path == case / 'verification-metadata.json', 'oracle metadata relocation is not yet classified')
        metadata = e.read(metadata_path)
        require(int(metadata['case_id']) == int(case.name.removeprefix('case_')), 'oracle case identity differs')
        if 'verifier' in verify:
            require(verify['verifier'] == oracle_ref, 'executed original oracle differs')
            e.bound(verify['metadata'], metadata_path)
            for ref in verify.get('oracle_dependencies', []):
                e.bound(ref, binary=True)
        native_path = case / 'native/execution.json' if root.name == 'standalone' else case / 'native.execution.json'
        native = e.read(native_path)
        process(native)
        if root.name == 'standalone':
            binary = build['standalone']
            e.bound(binary, binary=True)
            require(native.get('argv', [None])[0] == binary['path'], 'native standalone binary differs')
        else:
            native_record = e.read(case / 'native.json')
            role = request.get('role')
            identity = build.get('roles', {}).get(role, {})
            require(identity and native_record.get('source_sha256') == identity.get('source_sha256')
                    and native_record.get('kernel_symbols') == identity.get('kernel_symbols')
                    and native_record.get('mode') == 'correctness' and native_record.get('exit_code') == 0
                    and all(native_record.get(k) is True for k in ('stream_destroyed', 'context_destroyed', 'finalized')),
                    'prepared native correctness/teardown/source proof is incomplete')
        result_name = 'precision.json' if (case / 'precision.json').is_file() else 'result.json'
        result = e.read(case / result_name)
        require(result.get('passed', result.get('precision_pass')) is False
                and result.get('case_id') == metadata['case_id'], 'original verifier has no explicit failed numeric result')
        stdout_path = Path(str(verify_path).removesuffix('.execution.json') + '.stdout.log') if verify_path.name != 'execution.json' else verify_path.parent / 'stdout.log'
        stdout = e.read(stdout_path, text=True)
        objects = []
        for line in stdout.splitlines():
            try:
                objects.append(json.loads(line))
            except (ValueError, TypeError):
                pass
        require(result in objects, 'oracle stdout does not corroborate its failed numeric result')
        # Include produced bytes in failure closure; no missing output counts as
        # numeric evidence, even when the verifier happened to write a result.
        outputs = [Path(v) for k, v in metadata.items() if isinstance(v, str)
                   and (k == 'output' or k.startswith('output_') or k.endswith('_out') or k.endswith('_output'))]
        require(outputs, 'oracle output binding is absent')
        for path in outputs:
            require(path.is_relative_to(case), 'oracle output is outside private correctness case')
            e.file(path)
        return 'original_oracle_numeric_mismatch', 'Healthy completed native execution failed the hash-bound original numeric oracle.'
    raise Unproven('no positively proven original-oracle numeric failure')


def dispatch_failure(e, task, parent, guard):
    root = parent / 'boundary-validation'
    require(e.read(root / 'completion.json') == guard, 'guard differs from recorded completion')
    require(not guard.get('error') and not guard.get('verification_error'),
            'guard preparation, health or verifier error is not positively attributed to source')
    request = e.bound(guard.get('request'), root / 'request.json')
    require(request.get('candidate') == parent.name and request.get('dispatch_logs_required') is True,
            'guard does not bind candidate dispatch')
    e.bound(request.get('script'), task / 'agent/boundary_guard.py', text=True)
    plan = e.bound(request.get('dispatch_plan'), parent / 'dispatch_plan.json')
    build = e.read(parent / 'build/build_manifest.json')
    require(request.get('binary') == build.get('standalone'), 'guard binary differs from build')
    e.bound(request['binary'], binary=True)
    health(e, root)
    for name in ('prepare', 'verify'):
        process(e.read(root / name / 'execution.json'))
    commands = e.read(root / 'inputs/coordinator_commands.json')
    rows = guard.get('cases', [])
    require(len(rows) == len(commands) and rows, 'guard coverage is incomplete')
    expected = {r['tiling_key']: r['kernel_entry'] for r in [*plan['entries'], plan['fallback']]}
    mismatch = False
    for row, command in zip(rows, commands):
        require(row.get('name') == command.get('name') and re.fullmatch(r'[A-Za-z0-9_-]+', row['name']),
                'guard command ordering or name differs')
        require(not row.get('error') and command.get('expected_exit') != 'nonzero',
                'native guard exit is not a successful dispatch check')
        directory = root / 'executions' / row['name']
        native = e.bound(row.get('execution'), directory / 'execution.json')
        process(native)
        require(native.get('argv') == [request['binary']['path'], *command['argv']], 'guard actual argv differs')
        require(row.get('expected_process_passed') is True, 'guard process check was not successful')
        key = command.get('expected_key')
        require(type(key) is int and key in expected and command.get('expected_entry', expected[key]) == expected[key],
                'guard expected entry is absent from the bound dispatch plan')
        logs = [json.loads(line.split('APROF_DISPATCH_JSON:', 1)[1])
                for line in e.read(directory / 'stdout.log', text=True).splitlines()
                if line.startswith('APROF_DISPATCH_JSON:')]
        require(logs == row.get('dispatch_logs'), 'recorded dispatch differs from actual stdout')
        passed = (len(logs) == 1 and type(logs[0].get('tiling_key')) is int
                  and logs[0]['tiling_key'] == key and logs[0].get('kernel_entry') == expected[key])
        require(row.get('dispatch_log_passed') is passed, 'guard dispatch outcome contradicts stdout')
        mismatch |= not passed
    require(mismatch, 'guard has no actual bound dispatch mismatch')
    return 'actual_dispatch_mismatch', 'Healthy successful guard processes emitted dispatch inconsistent with their bound plan.'


REVIEWED_GROUP_NORM_GUARD = 'sha256:c9789d9ca9e48cd3b680650122c3ce8169d5d9549b492615537c7f15f79fe8a3'
# Vendored Huawei CANNBench Level2 group_norm/golden.py, CANN Open Software License v2.
REVIEWED_GROUP_NORM_GOLDEN = 'sha256:883644051a1954338a43d31c5ffeb0953a90d8b9b695f6423e54469f9647165c'
REVIEWED_GROUP_NORM_VERIFIER = 'sha256:9ef76d44b2af9b17cdca879632fbb4ec4c35f935b661045e8d85acfc752a0f70'


def boundary_execution_wrapper(e, record, cpu):
    """Corroborate declared argv with the actual retained shell invocation."""
    argv, shell = record.get('argv', []), record.get('shell_argv', [])
    require(isinstance(argv, list) and isinstance(shell, list) and len(shell) == len(argv) + 7
            and shell[:5] == ['taskset', '-c', cpu, 'bash', '-c']
            and shell[6:] == ['feedback-hardware', *argv], 'numeric guard actual shell argv differs')
    setup = shell[5]
    require(isinstance(setup, str), 'numeric guard setup command is missing')
    match = re.fullmatch(r'source (/[^\n ;]+/set_env\.sh) \|\| exit \$\?; '
        r'export LD_LIBRARY_PATH=/usr/local/Ascend/driver/lib64/common:'
        r'/usr/local/Ascend/driver/lib64/driver:\$\{LD_LIBRARY_PATH:-\}; exec "\$@"', setup)
    require(match is not None, 'numeric guard setup wrapper is unreviewed')
    e.file(match[1])


def boundary_event_prefix(e, task, parent, request_ref, completion_ref, manifest_ref, count):
    """Verify the historical linked prefix without binding future journal appends."""
    path = e.path(task / 'events.jsonl')
    previous, prepared, started, bindings = None, None, None, []
    for index, raw in enumerate(path.read_bytes().splitlines()):
        row = json.loads(raw); payload = {k: v for k, v in row.items() if k != 'hash'}
        digest = 'sha256:' + hashlib.sha256((json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                                        allow_nan=False) + '\n').encode()).hexdigest()
        require(row.get('sequence') == index and row.get('previous_hash') == previous and row.get('hash') == digest,
                'numeric guard public event prefix is not intact')
        previous = digest
        if row.get('kind') == 'boundary_cpu_prepared' and started is None:
            prepared = row
        if row.get('kind') == 'boundary_validation_started' and row.get('value', {}).get('candidate') == parent.name:
            require(started is None and row['value'].get('request') == request_ref,
                    'numeric guard start event differs')
            require(prepared and prepared['value'].get('manifest') == manifest_ref
                    and prepared['value'].get('count') == count and prepared['value'].get('hardware_executed') is False,
                    'numeric guard preparation was not declared before native execution')
            started = row
        if row.get('kind') == 'boundary_validation_completed' and row.get('value', {}).get('candidate') == parent.name:
            require(started is not None and row['value'].get('completion') == completion_ref,
                    'numeric guard completed event differs')
            for item in (prepared, started, row):
                bindings.append({'journal_path': str(path), 'sequence': item['sequence'],
                                 'event_hash': item['hash'], 'kind': item['kind']})
            e.event_bindings = bindings
            return
    raise Unproven('numeric guard lacks a completed public event prefix')


def boundary_numeric_failure(e, task, parent, guard):
    """Finite proof for the reviewed GN guard, including CPU oracle replay.

    Arbitrary verifier exit 1 is still insufficient. No guard or golden code is
    executed: known source hashes authorize the explicit CPU formula below.
    Unsupported operators/scripts/dtypes remain blocked. Historical process
    attribution relies on retained native records, as the existing oracle rule.
    """
    require(task.name == 'group_norm', 'no reviewed numeric boundary oracle for this operator')
    root = parent / 'boundary-validation'
    require(e.read(root / 'completion.json') == guard and not guard.get('error'),
            'numeric guard completion differs or records infrastructure failure')
    request = e.bound(guard.get('request'), root / 'request.json')
    require(request.get('operator') == 'group_norm' and request.get('candidate') == parent.name
            and request.get('dispatch_logs_required') is True, 'numeric guard identity differs')
    script = task / 'agent/boundary_guard.py'
    e.bound(request.get('script'), script, text=True)
    require(request['script']['sha256'] == REVIEWED_GROUP_NORM_GUARD, 'unreviewed numeric guard source')
    require(e.file(task / 'baseline/scripts/verify_result.py')['sha256'] == REVIEWED_GROUP_NORM_VERIFIER,
            'numeric guard original tolerance verifier is unreviewed')
    plan = e.bound(request.get('dispatch_plan'), parent / 'dispatch_plan.json')
    build = e.read(parent / 'build/build_manifest.json')
    require(build.get('operator') == 'group_norm' and request.get('binary') == build.get('standalone'),
            'numeric guard binary differs from operator build')
    e.bound(request.get('binary'), parent / 'build/build/standalone', binary=True)
    build_result = e.read(parent / 'stages/build/result.json')
    require(build_result.get('status') == 'passed' and build_result.get('candidate_id') == parent.name
            and build_result.get('kind') == 'build' and not build_result.get('error'), 'candidate build was not successful')
    build_plan = e.read(parent / 'stages/build/stage-plan.json')
    source_ref = e.file(parent / 'source.tar')
    require(build_plan.get('source_hash') == source_ref['sha256'] == plan.get('source_hash'),
            'numeric guard source/dispatch/build archive differs')
    native_files = {}
    with tarfile.open(parent / 'source.tar') as archive:
        names = set()
        for member in archive.getmembers():
            path = Path(member.name)
            require(not path.is_absolute() and '..' not in path.parts and member.name not in names
                    and (member.isfile() or member.isdir()), 'unsafe frozen numeric guard source member')
            names.add(member.name)
            parts = path.parts[1:] if path.parts and path.parts[0] == 'source' else path.parts
            if member.isfile() and parts and parts[0] in ('op_host', 'op_kernel'):
                relative = Path(*parts); source = parent / 'op' / relative
                require(str(relative) not in native_files, 'duplicate normalized original source')
                data = archive.extractfile(member).read(); e.file(source)
                require(source.read_bytes() == data, 'numeric guard original source differs from archive')
                native_files[str(relative)] = data
    actual_files = {str(p.relative_to(parent / 'op')) for name in ('op_host', 'op_kernel')
                    for p in (parent / 'op' / name).rglob('*') if p.is_file()}
    require(native_files and set(native_files) == actual_files, 'numeric guard native file set differs')
    native_hash = hashlib.sha256()
    for name, data in sorted(native_files.items()):
        native_hash.update(name.encode() + b'\0' + data + b'\0')
    require(set(build.get('roles', {})) == {'A', 'B'} and all(
        role.get('source_sha256') == native_hash.hexdigest()
        and role.get('source_dir') == str(parent / 'op') for role in build['roles'].values()),
        'numeric guard source identity differs from built roles')
    health(e, root)
    prepare = e.read(root / 'prepare/execution.json'); process(prepare)
    verify = e.read(root / 'verify/execution.json'); process(verify, 1)
    argv = verify.get('argv', [])
    require(isinstance(argv, list) and len(argv) == 8 and Path(argv[0]).is_absolute()
            and Path(argv[0]).name.startswith('python')
            and argv[1:] == ['-B', str(script), '--output', str(root / 'inputs'), '--verify', '--plan', str(parent / 'dispatch_plan.json')],
            'numeric verifier argv differs')
    expected_error = f'process failed (1): {argv[0]}'
    require(verify.get('error') == expected_error and guard.get('verification_error') == {
        'type': 'RuntimeError', 'message': expected_error}, 'numeric verifier termination is unrecognized')
    require(prepare.get('argv') == [argv[0], '-B', str(script), '--output', str(root / 'inputs'), '--plan', str(parent / 'dispatch_plan.json')],
            'numeric guard preparation argv differs')
    for label, record in [('prepare', prepare), ('verify', verify)]:
        require(record.get('cwd') == str(task) and record.get('environment_overrides') == {},
                'numeric guard execution environment differs')
        require(not e.read(root / label / 'stderr.log', text=True).strip(), 'numeric guard process stderr is not empty')
        boundary_execution_wrapper(e, record, '40-43')
    commands = e.read(root / 'inputs/coordinator_commands.json')
    specification = e.read(task / 'agent/boundary_cases.json')
    verification = e.read(root / 'inputs/verification.json')
    prepared = e.read(root / 'inputs/cpu_preparation.json')
    rows, cases, results = guard.get('cases', []), specification.get('cases', []), verification.get('results', [])
    require(specification.get('operator') == verification.get('operator') == prepared.get('operator') == 'group_norm'
            and verification.get('hardware_executed_by_this_script') is False
            and prepared.get('hardware_executed_by_this_script') is False
            and len(rows) == len(cases) == len(commands) == len(results) == len(prepared.get('results', []))
            and 0 < len(rows) <= 32, 'numeric guard coverage is incomplete')
    manifest_path = task / 'agent/boundary_inputs/coordinator_commands.json'
    manifest = e.read(manifest_path)
    require(manifest.get('operator') == 'group_norm' and manifest.get('hardware_executed') is False
            and len(manifest.get('commands', [])) == len(cases), 'numeric guard original preparation manifest differs')
    boundary_event_prefix(e, task, parent, e.file(root / 'request.json'), e.file(root / 'completion.json'),
                          e.file(manifest_path), len(cases))
    require(json.loads(e.read(root / 'verify/stdout.log', text=True)) == {
        'operator': 'group_norm', 'cases': len(rows), 'mode': 'verify_existing_outputs', 'passed': False},
        'numeric verification stdout contradicts result')
    require(json.loads(e.read(root / 'prepare/stdout.log', text=True)) == {
        'operator': 'group_norm', 'cases': len(rows), 'mode': 'cpu_only', 'passed': True},
        'numeric guard preparation stdout contradicts result')
    try:
        import numpy as np
        import torch
        from aprof_runtime.planning import select_dispatch
        from level2_adapters import workload_metadata
    except ImportError as exc:
        raise Unproven('CPU numeric replay dependencies unavailable: ' + str(exc)) from exc
    # Record actual replay dependencies; do not execute arbitrary oracle sources.
    for path in (np.__file__, torch.__file__, torch.nn.functional.__file__, torch._C.__file__):
        e.file(path)
    golden = task / 'agent/reference/golden.py'
    require(e.file(golden)['sha256'] == REVIEWED_GROUP_NORM_GOLDEN, 'numeric guard golden is not the reviewed original')
    names = set(); numeric_mismatch = False
    for row, case, command, result, preparation in zip(rows, cases, commands, results, prepared['results']):
        name = case.get('name')
        require(isinstance(name, str) and re.fullmatch(r'[A-Za-z0-9_-]+', name) and name not in names,
                'numeric guard case name is invalid or duplicated')
        names.add(name)
        require(row.get('name') == command.get('name') == result.get('name') == preparation.get('name') == name,
                'numeric guard case ordering differs')
        descriptor = case['metadata']; attrs = descriptor['attributes']; shape = descriptor['shape']; dtype = descriptor['dtype']
        require(isinstance(shape, list) and 2 <= len(shape) <= 8 and all(type(n) is int and n > 0 for n in shape)
                and math.prod(shape) <= 1_000_000 and dtype in ('float16', 'float32', 'bfloat16'), 'unsupported numeric guard shape/dtype')
        require(type(attrs.get('num_groups')) is int and attrs['num_groups'] > 0 and shape[1] % attrs['num_groups'] == 0
                and type(attrs.get('epsilon')) in (float, int) and math.isfinite(attrs['epsilon']) and attrs['epsilon'] > 0,
                'unsupported group norm parameters')
        metadata = workload_metadata('group_norm', {**attrs, 'shape': shape, 'dtype': dtype, 'attrs': attrs})
        selected = select_dispatch(plan, metadata)
        require(command.get('metadata') == metadata and result.get('dispatch') == preparation.get('dispatch') == selected
                and case.get('expected_key') == command.get('expected_key') == selected['tiling_key']
                and command.get('expected_entry') == selected['kernel_entry'], 'numeric guard semantic dispatch differs')
        source = task / 'agent/boundary_inputs' / name; dest = root / 'inputs' / name
        declaration = e.read(source / 'guard.json')
        require(declaration == manifest['commands'][len(names) - 1], 'numeric guard declaration differs from the public prepared manifest')
        require(declaration.get('name') == name and declaration.get('operator') == 'group_norm'
                and declaration.get('hardware_executed') is False and declaration.get('workload_metadata') == descriptor
                and declaration.get('expected_key') == selected['tiling_key'], 'numeric guard declaration differs')
        e.bound(declaration.get('producer'), task / 'agent/prepare_boundary_inputs.py', text=True)
        e.bound(declaration.get('oracle'), golden, text=True)
        require(result.get('oracle') == preparation.get('oracle') == declaration['oracle']
                and result.get('reference_status') == preparation.get('reference_status') == declaration.get('reference_status'),
                'numeric guard reference identity differs')
        expected_ref = e.bound(declaration.get('expected'), source / 'expected.bin', binary=True)
        require(e.file(dest / 'expected.bin')['sha256'] == expected_ref['sha256']
                and command.get('reference') == str(dest / 'expected.bin'), 'numeric guard expected bytes differ')
        for filename in ('x.bin', 'gamma.bin', 'beta.bin'):
            require(e.file(source / filename)['sha256'] == e.file(dest / filename)['sha256'], 'numeric guard input bytes differ')
        expected_args = ['--shape', ','.join(map(str, shape)), '--dtype', dtype, '--groups', str(attrs['num_groups']),
                         '--epsilon', str(attrs['epsilon']), '--x', str(dest / 'x.bin'), '--gamma', str(dest / 'gamma.bin'),
                         '--beta', str(dest / 'beta.bin'), '--output', str(dest / 'output.bin'), '--device', '0']
        declared_args = [value.replace(str(source), str(dest)).replace('{device}', '0') for value in declaration['native_arguments']]
        require(command.get('argv') == declared_args == expected_args, 'numeric guard actual input/output argv differs')
        directory = root / 'executions' / name
        native = e.bound(row.get('execution'), directory / 'execution.json'); process(native)
        require(native.get('argv') == [request['binary']['path'], *expected_args]
                and native.get('cwd') == str(parent / 'op') and native.get('environment_overrides') == {}
                and not row.get('error') and row.get('expected_process_passed') is True,
                'numeric guard native process identity differs')
        boundary_execution_wrapper(e, native, '8')
        stdout = e.read(directory / 'stdout.log', text=True)
        require(not e.read(directory / 'stderr.log', text=True).strip(), 'numeric guard native stderr is not empty')
        logs = [json.loads(line.split('APROF_DISPATCH_JSON:', 1)[1]) for line in stdout.splitlines()
                if line.startswith('APROF_DISPATCH_JSON:')]
        expected_log = {'tiling_key': selected['tiling_key'], 'kernel_entry': selected['kernel_entry']}
        require(logs == row.get('dispatch_logs') == [expected_log] and row.get('dispatch_log_passed') is True,
                'numeric guard has a missing or mismatched actual dispatch')
        def read_array(path, count):
            e.file(path)
            storage_dtype = {'float16': np.float16, 'float32': np.float32, 'bfloat16': np.uint16}[dtype]
            require(path.stat().st_size == count * np.dtype(storage_dtype).itemsize,
                    'numeric guard byte length differs from shape/dtype')
            raw = np.fromfile(path, storage_dtype)
            require(raw.size == count, 'numeric guard data size differs')
            return (raw.astype(np.uint32) << 16).view(np.float32) if dtype == 'bfloat16' else raw
        n = math.prod(shape); actual = read_array(dest / 'output.bin', n); expected = read_array(dest / 'expected.bin', n)
        x = read_array(dest / 'x.bin', n); gamma = read_array(dest / 'gamma.bin', shape[1]); beta = read_array(dest / 'beta.bin', shape[1])
        require(all(np.isfinite(value).all() for value in (x, gamma, beta, actual, expected)), 'nonfinite numeric boundary proof is unsupported')
        try:
            torch_dtype = getattr(torch, dtype)
            replay = torch.nn.functional.group_norm(torch.from_numpy(x.copy()).reshape(shape).to(torch_dtype), attrs['num_groups'],
                torch.from_numpy(gamma.copy()).to(torch_dtype), torch.from_numpy(beta.copy()).to(torch_dtype), attrs['epsilon'])
            replay_bytes = replay.contiguous().view(torch.uint8).numpy().tobytes()
        except RuntimeError as exc:
            raise Unproven('CPU original golden replay failed: ' + str(exc)) from exc
        require(replay_bytes == (dest / 'expected.bin').read_bytes(),
                'stored numeric guard reference differs from original golden CPU replay')
        diff = np.abs(actual.astype(np.float32) - expected.astype(np.float32)); rel = diff / (np.abs(expected.astype(np.float32)) + 1e-7)
        threshold = .01 if dtype == 'bfloat16' else .005
        metrics = {'passed': bool(rel.mean(dtype=np.float64) < threshold and rel.max(initial=0) < 10 * threshold),
                   'special_values_match': True, 'mere': float(rel.mean(dtype=np.float64)),
                   'mare': float(rel.max(initial=0)), 'threshold': threshold}
        require(result.get('output') == metrics and result.get('passed') is metrics['passed']
                and result.get('status') == ('coordinator_output_verified' if metrics['passed'] else 'coordinator_output_failed'),
                'numeric guard result does not replay from actual bytes')
        if not metrics['passed']:
            require(dtype == 'float32', 'only finite float32 GN numeric failures have a reviewed positive proof')
            # Original baseline verifier grants this absolute tolerance. It must
            # still fail, so a stricter supplemental guard cannot cause admission.
            canonical_rel = np.where(diff <= 5e-5, np.float32(0), rel)
            require(not (canonical_rel.mean(dtype=np.float64) < threshold and canonical_rel.max(initial=0) < 10 * threshold),
                    'numeric guard only fails a stricter-than-original tolerance')
            numeric_mismatch = True
    require(numeric_mismatch, 'numeric guard has no original-oracle numeric mismatch')
    return 'original_boundary_oracle_numeric_mismatch', 'Retained successful native GN records, bound dispatch and original-golden CPU replay consistently show a numeric mismatch; historical raw outputs and verification were not individually presealed.'


REVIEWED_RMS_GUARD = 'sha256:888272f3b4f4138584d1ad0ceb0751defdf76951c44b4ce7c9a8c436c523fe29'
REVIEWED_RMS_SPEC = 'sha256:028abfe282135dcf42309da65e52441c5b15574c16008882a6db36e1a5ac286e'
REVIEWED_RMS_VERIFIER = 'sha256:5dc773c336cef836e2173b584c2b20399eb073347722dba321126f3c03821955'
RMS_BENIGN_STDERR = ('/usr/local/python3.11.15/lib/python3.11/site-packages/redis/connection.py:77: UserWarning: redis-py works best with hiredis. Please consider installing\n'
                     '  warnings.warn(msg)\n')


def rms_boundary_events(e, task, parent, request_ref, completion_ref):
    path=e.path(task/'events.jsonl');previous=None;start=None
    for index,raw in enumerate(path.read_bytes().splitlines()):
        row=json.loads(raw);payload={k:v for k,v in row.items() if k!='hash'}
        h='sha256:'+hashlib.sha256((json.dumps(payload,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode()).hexdigest()
        require(row.get('sequence')==index and row.get('previous_hash')==previous and row.get('hash')==h,'RMS guard event prefix differs')
        previous=h
        if row.get('kind')=='boundary_validation_started' and row.get('value',{}).get('candidate')==parent.name:
            require(start is None and row['value'].get('request')==request_ref,'RMS guard start differs');start=row
        if row.get('kind')=='boundary_validation_completed' and row.get('value',{}).get('candidate')==parent.name:
            require(start and row['value'].get('completion')==completion_ref,'RMS guard completion event differs')
            e.event_bindings=[{'journal_path':str(path),'sequence':r['sequence'],'event_hash':r['hash'],'kind':r['kind']} for r in (start,row)]
            return
    raise Unproven('RMS guard public completion absent')


def rms_registered_build(e,task,parent,request,source_ref,build_result):
    from msprof_exploration_campaign import Campaign
    ledger=Campaign(task.parents[1]/'ledger');state=ledger.state['tasks'][task.name]
    candidate=state.get('candidates',{}).get(parent.name)
    require(isinstance(candidate,dict) and candidate.get('source_hash')==source_ref['sha256'] and candidate.get('artifacts',{}).get('source')==source_ref and candidate['artifacts'].get('dispatch_plan')==request['dispatch_plan'],'RMS registered source/dispatch differs')
    stage_id=parent.name+'-build';stage=state.get('stages',{}).get(stage_id,{})
    require(stage.get('candidate_id')==parent.name and stage.get('kind')=='build' and stage.get('plan',{}).get('source_hash')==source_ref['sha256'] and stage.get('attempts'),'RMS registered build stage differs')
    attempt=stage['attempts'][-1];evidence=attempt.get('evidence',{})
    require(attempt.get('outcome')=='success' and evidence.get('build')==e.file(parent/'build/build_manifest.json') and evidence.get('result')==e.file(parent/'stages/build/result.json'),'RMS successful build evidence differs from ledger')
    bindings=[]
    for row in ledger.events:
        args=row['arguments']
        if args.get('workload')!=task.name:continue
        if (row['operation']=='register' and args.get('candidate_id')==parent.name) or (row['operation']=='finish' and args.get('stage_id')==stage_id and args.get('evidence')==evidence):
            bindings.append({key:row[key] for key in ('config_hash','event_id','sequence','hash','operation')})
    require(len(bindings)==2,'RMS source/build ledger evidence is ambiguous or absent')
    # Raw global ledger bytes are projected separately by the archive. Stable
    # event identities permit later appends without changing this classification.
    e.ledger_bindings=bindings


def rms_boundary_numeric_failure(e, task, parent, guard):
    """Only the reviewed ten-case RMS oracle and nonfinite-mask failure.

    Neither arbitrary exit1 nor a stricter guard tolerance is positive evidence.
    Every deterministic input/reference is reconstructed without executing the
    task's Python. The original functional.rms_norm must independently reject
    the actual special-value masks. Existing GN and compiler rules are unchanged.
    """
    require(task.name=='rms_norm','unreviewed RMS operator')
    root=parent/'boundary-validation'
    require(e.read(root/'completion.json')==guard and guard.get('version')=='level2_semantic_guards_v1' and not guard.get('error'),'RMS guard completion/infrastructure differs')
    request=e.bound(guard.get('request'),root/'request.json')
    require(request.get('operator')=='rms_norm' and request.get('candidate')==parent.name and request.get('dispatch_logs_required') is True and request.get('version')=='level2_semantic_guards_v1','RMS guard request differs')
    script=task/'agent/boundary_guard.py';e.bound(request.get('script'),script,text=True)
    require(request['script']['sha256']==REVIEWED_RMS_GUARD,'unreviewed RMS guard source')
    require(e.file(task/'agent/boundary_cases.json')['sha256']==REVIEWED_RMS_SPEC,'unreviewed RMS guard roster')
    require(e.file(task/'baseline/scripts/verify_result.py')['sha256']==REVIEWED_RMS_VERIFIER,'unreviewed original RMS verifier')
    plan=e.bound(request.get('dispatch_plan'),parent/'dispatch_plan.json')
    build = e.read(parent / 'build/build_manifest.json')
    require(build.get('operator') == 'rms_norm' and request.get('binary') == build.get('standalone'),
            'numeric guard binary differs from operator build')
    e.bound(request.get('binary'), parent / 'build/build/standalone', binary=True)
    build_result = e.read(parent / 'stages/build/result.json')
    require(build_result.get('status') == 'passed' and build_result.get('candidate_id') == parent.name
            and build_result.get('kind') == 'build' and not build_result.get('error'), 'candidate build was not successful')
    build_plan = e.read(parent / 'stages/build/stage-plan.json')
    source_ref = e.file(parent / 'source.tar')
    require(build_plan.get('source_hash') == source_ref['sha256'] == plan.get('source_hash'),
            'numeric guard source/dispatch/build archive differs')
    native_files = {}
    with tarfile.open(parent / 'source.tar') as archive:
        names = set()
        for member in archive.getmembers():
            path = Path(member.name)
            require(not path.is_absolute() and '..' not in path.parts and member.name not in names
                    and (member.isfile() or member.isdir()), 'unsafe frozen numeric guard source member')
            names.add(member.name)
            parts = path.parts[1:] if path.parts and path.parts[0] == 'source' else path.parts
            if member.isfile() and parts and parts[0] in ('op_host', 'op_kernel'):
                relative = Path(*parts); source = parent / 'op' / relative
                require(str(relative) not in native_files, 'duplicate normalized original source')
                data = archive.extractfile(member).read(); e.file(source)
                require(source.read_bytes() == data, 'numeric guard original source differs from archive')
                native_files[str(relative)] = data
    actual_files = {str(p.relative_to(parent / 'op')) for name in ('op_host', 'op_kernel')
                    for p in (parent / 'op' / name).rglob('*') if p.is_file()}
    require(native_files and set(native_files) == actual_files, 'numeric guard native file set differs')
    native_hash = hashlib.sha256()
    for name, data in sorted(native_files.items()):
        native_hash.update(name.encode() + b'\0' + data + b'\0')
    require(set(build.get('roles', {})) == {'A', 'B'} and all(
        role.get('source_sha256') == native_hash.hexdigest()
        and role.get('source_dir') == str(parent / 'op') for role in build['roles'].values()),
        'numeric guard source identity differs from built roles')
    rms_registered_build(e,task,parent,request,source_ref,build_result)
    health(e,root)
    prepare=e.read(root/'prepare/execution.json');process(prepare)
    verify=e.read(root/'verify/execution.json');process(verify,1)
    argv=verify.get('argv',[])
    require(isinstance(argv,list) and len(argv)==8 and Path(argv[0]).is_absolute() and Path(argv[0]).name.startswith('python') and argv[1:]==['-B',str(script),'--output',str(root/'inputs'),'--verify','--plan',str(parent/'dispatch_plan.json')],'RMS verify argv differs')
    error=f'process failed (1): {argv[0]}'
    require(verify.get('error')==error and guard.get('verification_error')=={'type':'RuntimeError','message':error},'RMS verifier failure is not normal exit1')
    require(prepare.get('argv')==[argv[0],'-B',str(script),'--output',str(root/'inputs'),'--plan',str(parent/'dispatch_plan.json')],'RMS prepare argv differs')
    for label,record in [('prepare',prepare),('verify',verify)]:
        require(record.get('cwd')==str(task) and record.get('environment_overrides')=={},'RMS CPU process environment differs')
        stderr=e.read(root/label/'stderr.log',text=True)
        require(stderr in ('',RMS_BENIGN_STDERR),'RMS CPU stderr contains an unreviewed error/warning')
        if stderr:e.file(Path('/usr/local/python3.11.15/lib/python3.11/site-packages/redis/connection.py'))
        boundary_execution_wrapper(e,record,'40-43')
    spec=e.read(task/'agent/boundary_cases.json');commands=e.read(root/'inputs/coordinator_commands.json')
    verified=e.read(root/'inputs/verification.json');prepared=e.read(root/'inputs/cpu_preparation.json')
    rows=guard.get('cases',[]);cases=spec.get('cases',[]);results=verified.get('results',[]);pre=prepared.get('results',[])
    require(spec.get('operator')==verified.get('operator')==prepared.get('operator')=='rms_norm' and verified.get('hardware_executed_by_this_script') is False and prepared.get('hardware_executed_by_this_script') is False and len(rows)==len(cases)==len(results)==len(pre)==len(commands)==10,'RMS reviewed ten-case coverage differs')
    rms_boundary_events(e,task,parent,e.file(root/'request.json'),e.file(root/'completion.json'))
    require(json.loads(e.read(root/'prepare/stdout.log',text=True))=={'operator':'rms_norm','cases':10,'mode':'cpu_only','passed':True},'RMS prepare stdout contradicts record')
    require(json.loads(e.read(root/'verify/stdout.log',text=True))=={'operator':'rms_norm','cases':10,'mode':'verify_existing_outputs','passed':False},'RMS verify stdout contradicts record')
    try:
        import torch
        import numpy as np
        from aprof_runtime.planning import select_dispatch
        from level2_adapters import workload_metadata
    except ImportError as exc:raise Unproven('RMS CPU replay unavailable: '+str(exc)) from exc
    for path in (torch.__file__,torch._C.__file__,torch.nn.functional.__file__,np.__file__):e.file(path)
    mismatch=False
    def bytes_of(tensor):return tensor.contiguous().view(torch.uint8).numpy().tobytes()
    for case,row,command,result,before in zip(cases,rows,commands,results,pre):
        name=case['name'];shape=case['shape'];dtype=case['dtype'];dt=getattr(torch,dtype);dest=root/'inputs'/name
        require(all(r.get('name')==name for r in (row,command,result,before)),'RMS case ordering differs')
        n=math.prod(shape);require(0<n<=1_000_000 and dtype in ('float16','float32','bfloat16'),'unsupported RMS guard shape/dtype')
        values=case.get('values')
        if values is not None:
            values=[{'nan':float('nan'),'inf':float('inf'),'-inf':-float('inf')}.get(v,v) if isinstance(v,str) else v for v in values]
            x=torch.tensor(values,dtype=dt).reshape(shape)
        else:x=(((torch.arange(n,dtype=torch.int64)*17%31)-15).float()/8).to(dt).reshape(shape)
        gamma=torch.linspace(.75,1.25,shape[-1]).to(dt)
        expected=(x.float()*torch.rsqrt((x.float()*x.float()).mean(dim=-1,keepdim=True)+case['epsilon'])*gamma.float()).to(dt)
        for filename,tensor in [('input.bin',x),('gamma.bin',gamma),('expected.bin',expected)]:
            e.file(dest/filename);require((dest/filename).read_bytes()==bytes_of(tensor),'RMS deterministic input/reference bytes differ')
        output=dest/'output.bin';e.file(output);storage={'float16':np.float16,'float32':np.float32,'bfloat16':np.uint16}[dtype]
        require(output.stat().st_size==n*np.dtype(storage).itemsize,'RMS output byte size differs')
        raw=torch.from_numpy(np.fromfile(output,storage).copy());actual=(raw.view(torch.bfloat16) if dtype=='bfloat16' else raw).reshape(shape)
        selected=select_dispatch(plan,workload_metadata('rms_norm',{'shape':shape,'dtype':dtype}))
        expected_args=['--shape',','.join(map(str,shape)),'--x',str(dest/'input.bin'),'--gamma',str(dest/'gamma.bin'),'--epsilon',str(case['epsilon']),'--dtype',dtype,'--output',str(output),'--device','0']
        require(command=={'name':name,'argv':expected_args,'expected_key':selected['tiling_key'],'reference':str(dest/'expected.bin')},'RMS command/dispatch differs')
        before_expected={'name':name,'dispatch':selected,'expected_shape':shape,'status':'cpu_reference_prepared_not_hardware_verified'}
        require(before==before_expected,'RMS CPU preparation differs')
        native=e.bound(row.get('execution'),root/'executions'/name/'execution.json');process(native)
        require(native.get('argv')==[request['binary']['path'],*expected_args] and native.get('cwd')==str(parent/'op') and native.get('environment_overrides')=={} and row.get('error') is None and row.get('expected_process_passed') is True,'RMS native identity or process differs')
        boundary_execution_wrapper(e,native,'8')
        stdout=e.read(root/'executions'/name/'stdout.log',text=True)
        require(not e.read(root/'executions'/name/'stderr.log',text=True).strip(),'RMS native stderr not empty')
        logs=[json.loads(line.split('APROF_DISPATCH_JSON:',1)[1]) for line in stdout.splitlines() if line.startswith('APROF_DISPATCH_JSON:')]
        require(logs==row.get('dispatch_logs')==[{'tiling_key':selected['tiling_key'],'kernel_entry':selected['kernel_entry']}] and row.get('dispatch_log_passed') is True,'RMS actual dispatch differs')
        special=lambda a,b:all(torch.equal(fn(a),fn(b)) for fn in (torch.isnan,torch.isposinf,torch.isneginf))
        masks=special(actual,expected);finite=expected.isfinite();threshold={'float16':2**-10,'float32':2**-13,'bfloat16':2**-7}[dtype]
        rel=(actual[finite].float()-expected[finite].float()).abs()/(expected[finite].float().abs()+1e-7)
        passed=bool(masks and (not finite.any() or (rel.double().mean()<threshold and rel.max()<10*threshold)))
        require(result=={**before_expected,'passed':passed,'status':'hardware_output_verified' if passed else 'hardware_output_failed'},'RMS verifier result does not replay')
        original=torch.nn.functional.rms_norm(x,(shape[-1],),gamma,eps=case['epsilon'])
        if not passed:
            require(not masks and special(expected,original) and not special(actual,original),'RMS positive rule requires original-oracle special-value mismatch, not stricter guard tolerance')
            mismatch=True
    require(mismatch,'RMS guard has no original-oracle special-value mismatch')
    return 'original_rms_boundary_nonfinite_mismatch', 'All ten retained successful native RMS guard processes and dispatch logs agree with deterministic reviewed input/reference replay; actual output special-value masks disagree with the original functional.rms_norm oracle. Historical output/verification bytes were not individually presealed; this is retained-artifact consistency attribution, not proof of an unrecorded runtime environment or a specific instruction cause.'


REVIEWED_CE_GUARD = 'sha256:c9789d9ca9e48cd3b680650122c3ce8169d5d9549b492615537c7f15f79fe8a3'
REVIEWED_CE_SPEC = 'sha256:d71f53d6447c01f175e5aca1507c6a46601ecde8323201365f129c37f142b70d'
REVIEWED_CE_VERIFIER = 'sha256:c9fb47df045980e8f7b6d54ac6da9f8ba961a2e2d9a4805a043b7e0dd59f001c'
REVIEWED_CE_GOLDEN = 'sha256:61be487f6e8218551f2149a586f07c749e48322b971ec94b79781cc2693edcd7'


def cross_entropy_boundary_numeric_failure(e, task, parent, guard):
    """Replay all thirteen reviewed CE guards against the original CPU golden.

    This proves retained output mismatch, not the cause inside a kernel. A changed
    guard, source, reference, native command, or threshold loses the attribution.
    """
    require(task.name == 'cross_entropy_loss' and parent.name == 'cross_entropy_loss001v2',
            'unreviewed CrossEntropyLoss candidate')
    root = parent / 'boundary-validation'
    require(e.read(root / 'completion.json') == guard and guard.get('status') == 'failed'
            and not guard.get('error'), 'CE guard completion differs')
    request = e.bound(guard.get('request'), root / 'request.json')
    require(request.get('operator') == task.name and request.get('candidate') == parent.name
            and request.get('dispatch_logs_required') is True, 'CE guard request differs')
    script = task / 'agent/boundary_guard.py'
    e.bound(request.get('script'), script, text=True)
    require(request['script']['sha256'] == REVIEWED_CE_GUARD
            and e.file(task / 'agent/boundary_cases.json')['sha256'] == REVIEWED_CE_SPEC
            and e.file(task / 'baseline/scripts/verify_result.py')['sha256'] == REVIEWED_CE_VERIFIER
            and e.file(task / 'agent/reference/golden.py')['sha256'] == REVIEWED_CE_GOLDEN,
            'CE guard, original verifier, or golden differs from reviewed bytes')
    plan = e.bound(request.get('dispatch_plan'), parent / 'dispatch_plan.json')
    build = e.read(parent / 'build/build_manifest.json')
    result = e.read(parent / 'stages/build/result.json')
    source_ref = e.file(parent / 'source.tar')
    require(build.get('operator') == task.name and result.get('status') == 'passed'
            and result.get('candidate_id') == parent.name and not result.get('error')
            and e.read(parent / 'stages/build/stage-plan.json').get('source_hash') == source_ref['sha256']
            and plan.get('source_hash') == source_ref['sha256']
            and request.get('binary') == build.get('standalone'), 'CE registered build differs')
    e.bound(request['binary'], parent / 'build/build/standalone', binary=True)
    from run_msprof_exploration_stage import verify_source_snapshot
    from collect_level1_traces import candidate_source_files
    verify_source_snapshot(parent / 'source.tar', parent / 'op')
    for path in candidate_source_files(parent / 'op').values():
        e.file(path)
    rms_registered_build(e, task, parent, request, source_ref, result)
    health(e, root)
    prepare = e.read(root / 'prepare/execution.json')
    verify = e.read(root / 'verify/execution.json')
    process(prepare); process(verify, 1)
    argv = verify.get('argv', [])
    require(isinstance(argv, list) and len(argv) == 8 and Path(argv[0]).is_absolute()
            and Path(argv[0]).name.startswith('python')
            and argv[1:] == ['-B', str(script), '--output', str(root / 'inputs'), '--verify', '--plan', str(parent / 'dispatch_plan.json')],
            'CE verifier argv differs')
    error = f'process failed (1): {argv[0]}'
    require(verify.get('error') == error and guard.get('verification_error') == {'type': 'RuntimeError', 'message': error}
            and prepare.get('argv') == [argv[0], '-B', str(script), '--output', str(root / 'inputs'), '--plan', str(parent / 'dispatch_plan.json')],
            'CE CPU verifier termination or preparation differs')
    for label, record in [('prepare', prepare), ('verify', verify)]:
        require(record.get('cwd') == str(task) and record.get('environment_overrides') == {},
                'CE guard CPU process environment differs')
        stderr = e.read(root / label / 'stderr.log', text=True)
        require(stderr in ('', RMS_BENIGN_STDERR), 'CE guard CPU stderr differs')
        boundary_execution_wrapper(e, record, '40-43')
    cases = e.read(task / 'agent/boundary_cases.json')['cases']
    commands = e.read(root / 'inputs/coordinator_commands.json')
    prepared = e.read(root / 'inputs/cpu_preparation.json')
    verified = e.read(root / 'inputs/verification.json')
    rows, before, results = guard.get('cases', []), prepared.get('results', []), verified.get('results', [])
    require(prepared.get('operator') == verified.get('operator') == task.name
            and prepared.get('hardware_executed_by_this_script') is False
            and verified.get('hardware_executed_by_this_script') is False
            and len(cases) == len(rows) == len(commands) == len(before) == len(results) == 13,
            'CE thirteen-case coverage differs')
    rms_boundary_events(e, task, parent, e.file(root / 'request.json'), e.file(root / 'completion.json'))
    require(json.loads(e.read(root / 'prepare/stdout.log', text=True)) ==
            {'operator': task.name, 'cases': 13, 'mode': 'cpu_only', 'passed': True}
            and json.loads(e.read(root / 'verify/stdout.log', text=True)) ==
            {'operator': task.name, 'cases': 13, 'mode': 'verify_existing_outputs', 'passed': False},
            'CE guard stdout contradicts completion')
    try:
        import numpy as np
        import torch
        from aprof_runtime.planning import select_dispatch
        from level2_adapters import workload_metadata
    except ImportError as exc:
        raise Unproven('CE CPU replay unavailable: ' + str(exc)) from exc
    for path in (np.__file__, torch.__file__, torch._C.__file__, torch.nn.functional.__file__):
        e.file(path)
    mismatch = set()
    for case, row, command, prior, observed in zip(cases, rows, commands, before, results):
        name = case['name']; descriptor = case['metadata']; shape = descriptor['shape']; dtype = descriptor['dtype']
        attrs = descriptor['attributes']; dest = root / 'inputs' / name; origin = task / 'agent/boundary_inputs' / name
        require(re.fullmatch(r'[A-Za-z0-9_-]+', name) and all(item.get('name') == name for item in (row, command, prior, observed))
                and isinstance(shape, list) and 2 <= len(shape) <= 8 and all(type(n) is int and n > 0 for n in shape)
                and math.prod(shape) <= 1_000_000 and dtype in ('float16', 'float32', 'bfloat16')
                and attrs.get('reduction') in ('none', 'sum', 'mean'), 'CE case scope or order differs')
        metadata = workload_metadata(task.name, {**attrs, 'shape': shape, 'dtype': dtype, 'attrs': attrs})
        selected = select_dispatch(plan, metadata)
        require(command.get('metadata') == metadata and prior.get('dispatch') == observed.get('dispatch') == selected
                and command.get('expected_key') == case.get('expected_key') == selected['tiling_key']
                and command.get('expected_entry') == selected['kernel_entry'], 'CE dispatch declaration differs')
        declaration = e.read(origin / 'guard.json')
        require(declaration.get('operator') == task.name and declaration.get('name') == name
                and declaration.get('workload_metadata') == descriptor
                and declaration.get('expected_key') == selected['tiling_key']
                and declaration.get('oracle') == observed.get('oracle') == prior.get('oracle')
                and declaration.get('reference_status') == observed.get('reference_status') == prior.get('reference_status'),
                'CE original guard declaration differs')
        e.bound(declaration['oracle'], task / 'agent/reference/golden.py', text=True)
        e.bound(declaration['expected'], origin / 'expected.bin', binary=True)
        for filename in ('input.bin', 'target.bin', 'expected.bin'):
            require(e.file(origin / filename)['sha256'] == e.file(dest / filename)['sha256'],
                    'CE original input or reference copy differs')
        arguments = [value.replace(str(origin), str(dest)).replace('{device}', '0')
                     for value in declaration['native_arguments']]
        require(command.get('argv') == arguments and command.get('reference') == str(dest / 'expected.bin'),
                'CE native argument declaration differs')
        native_root = root / 'executions' / name
        native = e.bound(row.get('execution'), native_root / 'execution.json'); process(native)
        require(native.get('argv') == [request['binary']['path'], *arguments]
                and native.get('cwd') == str(parent / 'op') and native.get('environment_overrides') == {}
                and row.get('expected_process_passed') is True and not row.get('error'),
                'CE native execution differs')
        boundary_execution_wrapper(e, native, '8')
        stdout = e.read(native_root / 'stdout.log', text=True)
        require(not e.read(native_root / 'stderr.log', text=True).strip(), 'CE native stderr differs')
        logs = [json.loads(line.split('APROF_DISPATCH_JSON:', 1)[1]) for line in stdout.splitlines()
                if line.startswith('APROF_DISPATCH_JSON:')]
        require(logs == row.get('dispatch_logs') == [{'tiling_key': selected['tiling_key'],
                'kernel_entry': selected['kernel_entry']}] and row.get('dispatch_log_passed') is True,
                'CE actual dispatch differs')
        storage = {'float16': np.float16, 'float32': np.float32, 'bfloat16': np.uint16}[dtype]
        size = math.prod(shape); target_size = shape[0] * math.prod(shape[2:]); output_size = target_size if attrs['reduction'] == 'none' else 1
        require((dest / 'input.bin').stat().st_size == size * np.dtype(storage).itemsize
                and (dest / 'target.bin').stat().st_size == target_size * 8
                and (dest / 'expected.bin').stat().st_size == (dest / 'output.bin').stat().st_size == output_size * np.dtype(storage).itemsize,
                'CE input or output size differs')
        actual_ref = e.file(dest / 'output.bin')
        raw = np.fromfile(dest / 'input.bin', storage).copy()
        tensor = torch.from_numpy(raw).view(torch.bfloat16) if dtype == 'bfloat16' else torch.from_numpy(raw)
        target = torch.from_numpy(np.fromfile(dest / 'target.bin', np.int64).copy()).reshape([shape[0], *shape[2:]])
        golden = torch.nn.functional.cross_entropy(tensor.reshape(shape), target,
                    reduction=attrs['reduction'], ignore_index=-100)
        require(golden.contiguous().reshape(-1).view(torch.uint8).numpy().tobytes() == (dest / 'expected.bin').read_bytes(),
                'CE original golden does not replay to reference bytes')
        def f32(path):
            raw = np.fromfile(path, storage)
            return (raw.astype(np.uint32) << 16).view(np.float32) if dtype == 'bfloat16' else raw
        actual, expected = f32(dest / 'output.bin'), f32(dest / 'expected.bin')
        special = bool(np.array_equal(np.isnan(actual), np.isnan(expected))
                       and np.array_equal(np.isposinf(actual), np.isposinf(expected))
                       and np.array_equal(np.isneginf(actual), np.isneginf(expected)))
        finite = np.isfinite(actual) & np.isfinite(expected)
        rel = np.abs(actual[finite].astype(np.float32) - expected[finite].astype(np.float32)) / (np.abs(expected[finite].astype(np.float32)) + 1e-7)
        threshold = {'float32': 2**-13, 'float16': 2**-10, 'bfloat16': 2**-7}[dtype]
        mere = float(rel.mean(dtype=np.float64)) if rel.size else 0.
        mare = float(rel.max(initial=0))
        metrics = {'passed': bool(special and mere < threshold and mare < 10 * threshold),
                   'special_values_match': special, 'mere': mere,
                   'mare': mare, 'threshold': threshold}
        require(observed.get('output') == metrics and observed.get('passed') is metrics['passed']
                and observed.get('status') == ('coordinator_output_verified' if metrics['passed'] else 'coordinator_output_failed'),
                'CE verifier result does not replay from native output')
        if not metrics['passed']:
            require(special and rel.size and float(rel.mean(dtype=np.float64)) >= threshold,
                    'CE failure is not a finite mismatch beyond original tolerance')
            mismatch.add(name)
    require(mismatch == {'sum_partial_tail', 'capacity_769_sum'}, 'CE reviewed failure set differs')
    return 'original_ce_boundary_numeric_mismatch', ('Retained native outputs, dispatch, original golden CPU replay and original '
            'dtype tolerances agree on two reduced-loss boundary mismatches. This attributes the observed outputs, not a kernel instruction cause.')


def classify_failure(task, parent, stage=None, guard=None):
    """Return a deterministic evidence-bound classification; never execute or write.

    ``stage`` is the first failed, already ledger-bound result, or None when only
    semantic guards failed. Callers must freeze/replay this result in feedback.
    """
    e = Evidence()
    status, rule, reason = 'infrastructure_blocked', 'unproven_failure', 'No positive source-failure proof.'
    try:
        task, parent = canonical_path(task), canonical_path(parent)
        require(parent.parent == task / 'candidates', 'candidate is outside the task')
        if stage is not None:
            require(stage.get('status') == 'failed', 'stage is not a failed terminal execution')
            directory = stage_location(e, parent, stage)
            require(not infra_error(stage.get('error')), 'stage records an infrastructure exception')
            if stage.get('kind') == 'build':
                rule, reason = compiler_failure(e, parent, stage)
            elif stage.get('kind') == 'correctness':
                rule, reason = verifier_failure(e, task, parent, stage, directory)
            else:
                raise Unproven('measurement/runtime/unsupported stage remains unfinished')
        else:
            require(guard is not None and guard.get('status') == 'failed', 'no failed stage or guard')
            if guard.get('verification_error') is not None:
                rule, reason = (rms_boundary_numeric_failure(e, task, parent, guard) if task.name == 'rms_norm' else
                                cross_entropy_boundary_numeric_failure(e, task, parent, guard) if task.name == 'cross_entropy_loss' else
                                boundary_numeric_failure(e, task, parent, guard))
            else:
                rule, reason = dispatch_failure(e, task, parent, guard)
        status = 'source_attempt_failed'
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, OSError, OverflowError, tarfile.TarError) as exc:
        reason = str(exc)
    result = {'version': VERSION, 'status': status, 'rule': rule, 'reason': reason,
              'evidence': [e.refs[k] for k in sorted(e.refs)]}
    if hasattr(e, 'event_bindings'):
        result['event_bindings'] = e.event_bindings
    if hasattr(e, 'ledger_bindings'):
        result['ledger_bindings'] = e.ledger_bindings
    return result
