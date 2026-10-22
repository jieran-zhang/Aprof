from pathlib import Path
import datetime, hashlib, json, subprocess
ROOT=Path(__file__).resolve().parents[1]
PUB=ROOT/'public';PVT=ROOT/'private'
ORIG=Path('/mnt/tidalfs-hwwh01/dataset/dots_infra/workspace/jieran/APROF/aprof-maintenance-soft-targets-20261019/skill-libs/graph-base/1.3.0/workflows/references/source-regression-15/cases')
DIRECT=Path('/tmp/aprof-knowledge-sources-1SHAlx/direct')
DEVKIT=DIRECT/'asc-devkit'
MM=Path('examples/01_simd_cpp_api/00_introduction/03_fusion_operation/matmul_leakyrelu_basic_api')
DB=Path('examples/01_simd_cpp_api/05_best_practices/01_matrix_compute/matmul_basic_api_high_performance')
CP=Path('examples/01_simd_cpp_api/03_basic_api/00_data_movement/data_copy_pad_gm2ub_ub2gm')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,o):p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n')

timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
revisions=json.loads((DIRECT/'SOURCE_REVISIONS.json').read_text())
for r in revisions:
    result=subprocess.run(['git','-C',r['path'],'rev-parse','HEAD'],text=True,capture_output=True)
    r['verified_checkout_revision']=result.stdout.strip() if result.returncode==0 else None
    r['checkout_verified']=result.returncode==0 and r['verified_checkout_revision']==r['revision']
    assert r['checkout_verified'],r

manifest=[]
for p in sorted(PUB.rglob('*')):
    if not p.is_file():continue
    rel=p.relative_to(PUB);parts=rel.parts
    item={'public_path':str(rel),'sha256':sha(p),'bytes':p.stat().st_size,'source_origin':None,'role':None}
    origin=None;changed=False
    if parts[0]=='shared' and parts[1]=='rawdocs':
        origin=DEVKIT/Path(*parts[2:]);item['role']='complete_raw_api_document'
    elif str(rel)=='shared/licenses/asc-devkit.LICENSE':
        origin=DEVKIT/'LICENSE';item['role']='license'
    elif len(parts)>2 and parts[1]=='source':
        cid=parts[0];rest=Path(*parts[2:]);item['role']='implementation_source'
        if cid in ('case-01','case-03'):
            origin=ORIG/('case-01' if cid=='case-01' else 'case-12')/'source'/rest
        elif cid=='case-02':
            if parts[2] in ('upstream','current'):
                origin=DEVKIT/CP/parts[-1];changed=parts[2]=='current' and parts[-1]=='data_copy_pad.asc'
            else:item['role']='test_variant_delta'
        elif cid=='case-04':origin=DEVKIT/MM/rest
        elif cid=='case-05':
            if parts[2] in ('baseline','variant'):
                origin=DEVKIT/DB/parts[-1];changed=parts[2]=='variant' and parts[-1]=='mmad.asc'
            else:item['role']='test_variant_delta'
        elif cid=='case-06':
            if parts[2]=='vector':
                suffix=Path(*parts[3:]);mapping={'op_host/nacre.asc':'op_host/exp.asc','op_kernel/nacre_stage.asc':'op_kernel/exp_kernel.asc','op_kernel/nacre_plan.h':'op_kernel/exp_tiling.h','op_host/data_utils.h':'op_host/data_utils.h'}
                origin=ORIG/'case-01/source'/mapping[str(suffix)];changed=suffix.name!='data_utils.h'
            elif parts[2]=='cube':
                origin=DEVKIT/MM/('matmul_leakyrelu_basic_api.asc' if parts[-1]=='mica.asc' else parts[-1]);changed=parts[-1]=='mica.asc'
            else:item['role']='test_variant_delta'
    else:item['role']='evaluation_authored_task_or_shared_contract'
    if origin:
        assert origin.is_file(),origin
        item['source_origin']={'absolute_path':str(origin),'sha256':sha(origin),'source_unchanged_during_packaging':True}
        if origin.is_relative_to(DEVKIT):
            item['source_origin'].update({'repo':'asc-devkit','url':'https://gitcode.com/cann/asc-devkit',
                'revision':next(r['revision'] for r in revisions if r['repo']=='asc-devkit'),
                'repository_path':str(origin.relative_to(DEVKIT)),
                'license':'CANN Open Software License Agreement Version 2.0','license_sha256':sha(DEVKIT/'LICENSE')})
        else:
            item['source_origin'].update({'repo':'APROF repository_original_seed case snapshot',
                'revision_basis':'Exact original file sha256 and included upstream SOURCE-MANIFEST.json record',
                'license':'No license notice in supplied internal source headers; no third-party license invented.'})
        item['transformation']='test-only recorded delta' if changed else 'byte-for-byte copy'
        if not changed:assert sha(p)==sha(origin),(p,origin)
    else:item['transformation']='authored evaluation material'
    manifest.append(item)

# Check the raw snapshot manifests as an independent original-source checksum.
original_checks=[]
for cid in ['case-01','case-12']:
    base=ORIG/cid/'source';meta=json.loads((base/'SOURCE-MANIFEST.json').read_text())
    for f in meta['files']:
        if f['path'].startswith(('op_host/','op_kernel/')):
            actual=sha(base/f['path']);assert actual==f['sha256']
            original_checks.append({'case':cid,'path':f['path'],'sha256':actual,'matches_original_snapshot_manifest':True})

for p in (PVT/'gold').glob('case-*.json'):
    g=json.loads(p.read_text())
    for f in g['facts']:
        for s in f['sources']:
            fp=PUB/s['file'];assert sha(fp)==s['sha256']
            assert 1<=s['line_start']<=s['line_end']<=len(fp.read_text().splitlines())
    assert sum(f['points'] for f in g['facts'])==30

assert all('/private/' not in str(p.relative_to(PUB)) for p in PUB.rglob('*'))
assert not list(PUB.rglob('README*'))
assert not list(PUB.rglob('*gold*'))
assert not list(PUB.rglob('REPORT*'))
assert len({sha(PUB/f'case-{i:02}/workload/sdk-contract.md') for i in range(1,7)})==1

source_manifest={'schema':'aprof.code-understanding-source-manifest/v1','frozen_at_utc':timestamp,
    'verified_repositories':revisions,'files':manifest,'original_internal_snapshot_checks':original_checks,
    'scope':'Only eval-private was written. No hardware, SDK build, or evaluation agent calls were run.',
    'teaching_eval_separation':'No new skill draft read. Gold and helper results remain private; public holds tasks, original source and recorded test deltas only.',
    'license_note':'Full devkit license retained in public/shared/licenses; original copyright notices preserved in source and raw docs.'}
dump(PVT/'source_manifest.json',source_manifest)

cpu=json.loads((PVT/'results/cpu_checks.json').read_text());assert cpu['status']=='pass' and cpu['checks_passed']==6
assert json.loads((PVT/'results/scorer_check.json').read_text())['status']=='pass'
suite=json.loads((ROOT/'suite.json').read_text())
suite['state']='frozen_before_evaluation'
suite['frozen_at_utc']=timestamp
suite['freeze_manifest']='private/FREEZE.json'
suite['source_manifest']='private/source_manifest.json'
suite['grading_protocol']='private/GRADING_PROTOCOL.md'
suite['gold']={f'case-{i:02}':f'private/gold/case-{i:02}.json' for i in range(1,7)}
suite['cpu_results']='private/results/cpu_checks.json'
suite['design']['evaluation_agents_run_by_material_builder']=0
suite['shared_api_files_sha256']={str(p.relative_to(PUB)):sha(p) for p in sorted((PUB/'shared').rglob('*')) if p.is_file()}
for c in suite['cases']:
    c['public_files_sha256']={str(p.relative_to(PUB/c['id'])):sha(p) for p in sorted((PUB/c['id']).rglob('*')) if p.is_file()}
dump(ROOT/'suite.json',suite)

# This manifest intentionally contains no self hash. Evaluators must not mutate frozen inputs.
frozen_files=[ROOT/'suite.json',PVT/'GRADING_PROTOCOL.md',PVT/'source_manifest.json']
frozen_files+=sorted(p for p in PUB.rglob('*') if p.is_file())
frozen_files+=sorted((PVT/'gold').glob('case-*.json'))
frozen_files+=sorted(p for p in (PVT/'helpers').glob('*') if p.is_file())
frozen_files+=[PVT/'results/cpu_checks.json',PVT/'results/tiling_actual.json',PVT/'results/scorer_check.json']
freeze={'schema':'aprof.code-understanding-freeze/v1','frozen_at_utc':timestamp,'pre_evaluation':True,
        'files':{str(p.relative_to(ROOT)):sha(p) for p in frozen_files},
        'gold_fact_count':sum(len(json.loads(p.read_text())['facts']) for p in (PVT/'gold').glob('case-*.json')),
        'case_count':6,'planned_independent_agent_calls':24,'material_builder_agent_calls':0,
        'sdk_build':False,'hardware_run':False}
dump(PVT/'FREEZE.json',freeze)
report='''# Evaluation materials handoff

The six-case public suite and private gold are frozen before any evaluation call. `suite.json` is the runner index. It specifies 6 groups x 2 arms x 2 independent repeats = 24 calls. Both arms share only the frozen 1.3.0 `npu-arch` and `ascendc-api-best-practices` skills; B additionally receives the new `ascendc-code-understanding` skill. The common model was announced by the runner as `gpt-6.1-sol/high`; exact budgets remain runner-managed and must match across conditions.

Public material is under `public/case-01` through `public/case-06`. Each has complete source context and `workload/task.md`; every `sdk-contract.md` has identical bytes. `public/shared/rawdocs` contains 34 complete frozen devkit API documents, with exact revision/hashes and the retained license. No project README, teacher analysis, gold, helper result, or example answer is included in public material. Test-only deltas are explicit for the multi-row copy, reverse-event variant and identifier variants. Production originals are unchanged.

Private gold contains 59 stable fact IDs. Every case allocates 10 points each to algorithm/strategy, execution and hardware, for 30 per case and 180 per complete suite repeat. `private/GRADING_PROTOCOL.md` defines masked correct/partial/wrong/omitted/unsupported grading and explicit critical caps. `private/helpers/score_answer.py` only validates and aggregates annotations; it does not heuristically judge prose.

CPU validation passed all six checks in `private/results/cpu_checks.json`: direct calls to the original pure C++ Exp and Maximum tiling headers, byte-accurate multi-row copy/padding intervals, dispatch-linked broadcast address requests, labeled ND/NZ and L0 block packing, event partial order, and identifier equivalence/common contract. These helpers do not read gold. The scorer also passed synthetic full-score and critical-cap checks for all six cases. The only compilation used an ordinary C++ compiler for SDK-free tiling headers.

`private/source_manifest.json` records every public file, source revision/hash, transformation, license provenance and original internal snapshot checksum checks. `private/FREEZE.json` freezes public inputs, gold, helpers and validation evidence. The runner should copy only the current case plus shared documents and the assigned arm skills into each fresh agent workspace, never the entire eval-private directory. Keep condition mapping away from the grader until all masked scores are locked.

No NPU execution, Ascend SDK build, hardware simulation, skill-draft access, production source edits, or evaluation-agent calls were performed by the material builder. CPU models establish arithmetic, layout and ordering facts; they do not establish measured hardware failures, throughput, compiler acceptance or cross-platform deployment.
'''
(PVT/'REPORT.md').write_text(report)
print(json.dumps({'state':suite['state'],'public_files':len(manifest),'rawdocs':34,'facts':freeze['gold_fact_count'],'freeze_sha256':sha(PVT/'FREEZE.json'),'original_files_verified':len(original_checks)},ensure_ascii=False))
