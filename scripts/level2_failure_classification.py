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
    return 'original_source_kernel_type_inference', 'Retained completed ASC logs and fully replayed source/adapter/Make artifacts consistently attribute both role diagnostics to one original kernel; inherited Make environment and pre-execution recipe hashes were not recorded.'


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
            rule, reason = dispatch_failure(e, task, parent, guard)
        status = 'source_attempt_failed'
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, OSError, OverflowError, tarfile.TarError) as exc:
        reason = str(exc)
    return {'version': VERSION, 'status': status, 'rule': rule, 'reason': reason,
            'evidence': [e.refs[k] for k in sorted(e.refs)]}
