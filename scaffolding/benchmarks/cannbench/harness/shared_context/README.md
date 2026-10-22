# Native shared-context prepared timing

`shared_context_paired_v1` uses one native process for an entire case suite. The
runner is the only owner of ACL initialization and its explicit context/stream.
Two ASC shared objects expose the C ABI in `abi.h`; each kernel and generated stub
has a role/source-specific name. `RTLD_LOCAL` and `-Bsymbolic` prevent interposition
between same-source A/A roles. This runner never launches role subprocesses.

Build without executing hardware:

```sh
source /usr/local/Ascend/ascend-toolkit/set_env.sh
python scaffolding/collection/scripts/shared_context_build.py --operator exp \
  --source-a /absolute/baseline --source-b /absolute/candidate \
  --output-dir /absolute/new-build
```

The builder supports exp, mish, sigmoid, gelu, masked_scale,
foreach_addcdiv_scalar and foreach_norm. Original source trees are never edited.
Each generated source has a separate harness patch and hash. Kernel code and
source tiling functions are copied intact. Host tiling invocation and launch
configuration are extracted from the actual host; foreach chunk size comes from
its actual `kChunkElements` declaration. Legacy timing branches are removed only
from the generated adapter. Unsupported host layouts fail rather than silently
using default optimization parameters. New host algorithms require adapter review.

Cases are TSV with **one token per tab-separated field**, starting with case ID:

```text
case_1<TAB>--numel<TAB>1024<TAB>--dtype<TAB>float32<TAB>--input<TAB>/absolute/input.bin
```

Invoke `build/shared_context_runner` with `--role-a`, `--role-b`, `--cases`,
`--output-dir`, `--session-id`, `--device`, `--load-order AB|BA`,
`--first-order AB|BA`, and `--buffer-configs normal|swapped|normal,swapped|swapped,normal`.
Warmup is fixed at 10 complete calls per role, followed by 30 alternating AB/BA
pairs. Each role event measures 100 complete calls, divided by 100. Thirty pairs
mean sixty event samples, not thirty ABBA blocks. Every list member and both norm
partial/finalize kernels execute inside each complete call.

Inputs are independently prepared from the same files. Output and workspace
allocations are separate; `swapped` exchanges their physical pointer assignments
between roles while preserving role-specific tiling and inputs. This requires
matching resource layouts and fails explicitly when the layouts differ. The same
physical slots are retained across configurations, so allocator reuse cannot
silently cancel the exchange or change input/tiling addresses. Input/tiling slots
stay with their logical role; their freshly prepared contents are copied into
the retained slots outside timing. Both configurations independently prepare
inputs/tilings and warm up. This control identifies the
output/workspace role factor; it does not exchange input allocations. Resources,
addresses, sizes, allocation order and policy are recorded in the journal.

`--verify-handshake yes` is the supervisor contract. After exporting both outputs
for a case/configuration, stdout emits a `validation_required` JSON record with
`case_id`, `buffer_config`, and `outputs: {A: path, B: path}`. Native execution waits
for stdin `ok\n`; any other acknowledgement or EOF fails the session before the
next configuration/case. The supervisor must run the frozen oracle before sending
`ok`. Without this flag, output records explicitly remain pending external
validation; the native process alone never claims correctness.

`journal.jsonl` is flushed per event and refuses overwrite. It includes process,
context/stream, module, preparation, resource, warmup, sample, output, validation,
failure and exit records. All samples have unique IDs, original ACL milliseconds,
explicit conversion, launch count and timestamps. Output scope is the final call
of the final formal sample; intermediate outputs are not claimed as checked.

Host/device locks, occupancy/health checks, affinity, input/oracle/source/binary
hash sealing, six-process schedules and statistics belong to the external
supervisor. Direct native invocation does not provide those controls. Build and
CPU tests do not establish hardware qualification.
