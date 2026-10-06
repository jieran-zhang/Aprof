"""Explicit candidate-bound GN guard revisions; legacy guards are never replaced.

Only the reviewed fixed runner is executable. A revision retains every old
input/reference byte and numeric rule, may declare additional original-oracle
cases, and is bound to source and dispatch before any native call.
"""
from pathlib import Path
import hashlib,json,math,re,shutil,sys

VERSION='level2_candidate_semantic_guard_contract_v1'
DRAFT_VERSION='level2_candidate_semantic_guard_draft_v1'
REQUEST_VERSION='level2_semantic_guards_v2'
ROOT=Path(__file__).resolve().parents[1]
REVIEWED_RUNNER_SHA='sha256:811c82dc647ee8e499b2828874a873e861a37c593fa979f5fa857a196602082c'
TOKEN=re.compile(r'[A-Za-z0-9_-]+\Z')
HASH=re.compile(r'sha256:[0-9a-f]{64}\Z')
UNSET=object()

def require(ok,message):
    if not ok:raise ValueError(message)

def safe(path,root=None):
    path=Path(path)
    require(path.is_absolute() and '..' not in path.parts and path==path.resolve(),'unaliased absolute guard path required')
    if root is not None:require(path.is_relative_to(root),'guard path escapes declared bundle')
    for part in (path,*path.parents):require(not part.is_symlink(),'guard symlink forbidden')
    require(path.is_file(),'guard file missing: '+str(path))
    return path

def pointer(path):
    path=safe(path);return {'path':str(path),'sha256':'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()}

def checked(ref,root=None):
    require(isinstance(ref,dict) and set(ref)=={'path','sha256'} and isinstance(ref['sha256'],str) and HASH.fullmatch(ref['sha256']),'invalid guard pointer')
    path=safe(ref['path'],root);require(pointer(path)==ref,'guard content hash differs');return path

def load(ref,root=None):return json.loads(checked(ref,root).read_bytes())

def context(task,parent):
    task,parent=Path(task),Path(parent)
    require(task.name=='group_norm' and parent.parent==task/'candidates' and TOKEN.fullmatch(parent.name),'unsupported candidate guard owner')
    return task,parent,parent/'semantic-guards'

def selection(contract,case):
    from aprof_runtime.planning import select_dispatch
    from level2_adapters import workload_metadata
    descriptor=case['metadata'];attrs=descriptor['attributes']
    semantic={key:attrs[key] for key in ('num_groups','epsilon')}
    metadata=workload_metadata('group_norm',{**semantic,'shape':descriptor['shape'],'dtype':descriptor['dtype'],'attrs':semantic})
    return select_dispatch(load(contract['dispatch_plan']),metadata),metadata

def read_array(path,dtype):
    import numpy as np
    raw=np.fromfile(path,{'float16':np.float16,'float32':np.float32,'bfloat16':np.uint16}[dtype])
    return (raw.astype(np.uint32)<<16).view(np.float32) if dtype=='bfloat16' else raw

def compare(actual,expected,dtype):
    import numpy as np
    require(actual.shape==expected.shape,'guard output shape differs')
    special=bool(np.array_equal(np.isnan(actual),np.isnan(expected)) and np.array_equal(np.isposinf(actual),np.isposinf(expected)) and np.array_equal(np.isneginf(actual),np.isneginf(expected)))
    finite=np.isfinite(actual)&np.isfinite(expected)
    rel=np.abs(actual[finite].astype(np.float32)-expected[finite].astype(np.float32))/(np.abs(expected[finite].astype(np.float32))+np.float32(1e-7))
    mere=float(rel.mean(dtype=np.float64)) if rel.size else 0.;mare=float(rel.max(initial=0));threshold=.01 if dtype=='bfloat16' else .005
    return dict(passed=bool(special and mere<threshold and mare<10*threshold),special_values_match=special,mere=mere,mare=mare,threshold=threshold)

def original_evidence(value):
    """Retained inputs are authorized by an already closed ledger observation."""
    from msprof_exploration_campaign import Campaign
    task=Path(value['task']);basis=value['original_observation']
    require(isinstance(basis,dict) and set(basis)=={'observation_id','feedback'} and isinstance(basis['observation_id'],str) and TOKEN.fullmatch(basis['observation_id']),'invalid original guard observation')
    path=checked(basis['feedback'],task/'feedback')
    require(path.parent==task/'feedback' and path.suffix=='.json','original guard feedback location differs')
    feedback=json.loads(path.read_bytes())
    state=Campaign(task.parents[1]/'ledger').state['tasks'][task.name]
    observation=state.get('observations',{}).get(basis['observation_id'])
    require(isinstance(observation,dict) and observation.get('close_feedback') is True and observation.get('report_ref')==basis['feedback']['sha256'] and observation.get('feedback')==feedback,'original guard observation is not immutable closed feedback')
    candidate=state.get('candidates',{}).get(observation.get('candidate_id'))
    require(isinstance(candidate,dict) and basis['observation_id'] in candidate.get('observation_ids',[]) and candidate.get('source_hash')==feedback.get('source_hash') and observation['candidate_id']==feedback.get('candidate_id'),'original guard observation source identity differs')
    classification=feedback.get('failure_classification',{})
    require(feedback.get('operator')=='group_norm' and feedback.get('status')=='source_attempt_failed' and classification.get('status')=='source_attempt_failed','original guard feedback is not a closed source failure')
    refs=classification.get('evidence')
    require(isinstance(refs,list) and refs,'original guard evidence missing')
    return {(ref['path'],ref['sha256']) for ref in refs if isinstance(ref,dict) and set(ref)=={'path','sha256'}}

def validate_cases(value,bundle,oracle):
    task=Path(value['task']);authority=original_evidence(value)
    def retained(ref):
        require((ref['path'],ref['sha256']) in authority,'retained guard bytes are absent from closed original evidence')
        return ref
    retained(value['original_spec']);retained(value['oracle'])
    original=load(value['original_spec'],task/'agent')
    require(value['original_spec']['path']==str(task/'agent/boundary_cases.json') and original['operator']=='group_norm','original guard spec differs')
    old=original['cases'];cases=value['cases'];require(isinstance(cases,list) and len(old)<=len(cases)<=32 and old,'retained guard coverage differs')
    names=set()
    for i,case in enumerate(cases):
        require(set(case)=={'name','metadata','expected_key','files','retained_from'},'unknown guard case fields')
        name=case['name'];require(isinstance(name,str) and TOKEN.fullmatch(name) and name not in names,'duplicate or unsafe guard name');names.add(name)
        descriptor=case['metadata'];require(set(descriptor)=={'shape','dtype','layout','attributes'},'guard metadata fields differ')
        shape,dtype,attrs=descriptor['shape'],descriptor['dtype'],descriptor['attributes']
        require(isinstance(shape,list) and 2<=len(shape)<=8 and all(type(n) is int and n>0 for n in shape) and math.prod(shape)<=1_000_000,'guard shape outside reviewed scope')
        require(dtype in ('float16','float32','bfloat16') and type(attrs.get('num_groups')) is int and attrs['num_groups']>0 and shape[1]%attrs['num_groups']==0,'guard dtype/groups invalid')
        require(type(attrs.get('epsilon')) in (float,int) and math.isfinite(attrs['epsilon']) and attrs['epsilon']>0,'guard epsilon invalid')
        require(descriptor['layout']=='ND','guard layout must match canonical contiguous ND input')
        selected,canonical=selection(value,case)
        require(set(attrs)<=set(canonical['attributes']) and all(type(val) is type(canonical['attributes'][key]) and val==canonical['attributes'][key] for key,val in attrs.items()),'guard attributes differ from canonical workload metadata')
        require(type(case['expected_key']) is int and selected['tiling_key']==case['expected_key'],'declared guard key differs from dispatch')
        require(set(case['files'])=={'x','gamma','beta','expected'},'guard input/output-reference closure differs')
        item=4 if dtype=='float32' else 2
        for key,ref in case['files'].items():
            path=checked(ref,bundle);require(path==bundle/'inputs'/name/(key+'.bin'),'guard file has noncanonical location')
            require(path.stat().st_size==(math.prod(shape) if key in ('x','expected') else shape[1])*item,'guard byte size differs')
        if i<len(old):
            prior=old[i];require(name==prior['name'] and descriptor==prior['metadata'],'retained guard metadata/order changed')
            origin=task/'agent/boundary_inputs'/name
            require(case['retained_from']==retained(pointer(origin/'guard.json')),'retained guard identity changed')
            for key,ref in case['files'].items():require(ref['sha256']==retained(pointer(origin/(key+'.bin')))['sha256'],'retained input or original golden changed')
        else:require(case['retained_from'] is None,'additional guard falsely claims retention')
        if oracle:
            import numpy as np
            import torch
            tensors={k:torch.from_numpy(read_array(ref['path'],dtype).copy()).to(getattr(torch,dtype)) for k,ref in case['files'].items() if k!='expected'}
            with torch.no_grad():expected=torch.nn.functional.group_norm(tensors['x'].reshape(shape),attrs['num_groups'],tensors['gamma'],tensors['beta'],attrs['epsilon'])
            require(expected.contiguous().view(torch.uint8).numpy().tobytes()==Path(case['files']['expected']['path']).read_bytes(),'guard golden differs from original GroupNorm oracle')

def checked_contract(ref,*,oracle=False,source_hash=None,dispatch_plan=None):
    value=load(ref);require(set(value)=={'version','operator','candidate_id','task','source_hash','dispatch_plan','script','draft','original_spec','original_observation','oracle','cases'},'unknown candidate guard contract fields')
    require(value['version']==VERSION and value['operator']=='group_norm' and TOKEN.fullmatch(value['candidate_id']),'candidate guard contract identity differs')
    task=Path(value['task']);parent=task/'candidates'/value['candidate_id'];task,parent,bundle=context(task,parent)
    require(Path(ref['path'])==bundle/'contract.json','candidate guard contract path differs')
    require(HASH.fullmatch(value['source_hash']) and (source_hash is None or value['source_hash']==source_hash),'candidate guard source differs')
    plan=load(value['dispatch_plan'],parent)
    require(value['dispatch_plan']['path']==str(parent/'dispatch_plan.json') and plan['operator']=='group_norm' and plan['source_hash']==value['source_hash'] and (dispatch_plan is None or value['dispatch_plan']==dispatch_plan),'candidate guard dispatch binding differs')
    script=checked(value['script'],bundle);require(script==bundle/'boundary_guard.py' and value['script']['sha256']==REVIEWED_RUNNER_SHA,'unreviewed candidate guard runner')
    draft=load(value['draft'],bundle);require(value['draft']['path']==str(bundle/'draft.json') and draft['version']==DRAFT_VERSION and draft['operator']=='group_norm' and draft['candidate_id']==parent.name,'candidate guard draft differs')
    require(value['original_spec']==draft['original_spec'] and value['original_observation']==draft['original_observation'] and value['oracle']==draft['oracle'],'original guard/oracle changed from author declaration')
    from level2_failure_classification import REVIEWED_GROUP_NORM_GOLDEN
    require(value['oracle']==pointer(task/'agent/reference/golden.py') and value['oracle']['sha256']==REVIEWED_GROUP_NORM_GOLDEN,'unreviewed original GN oracle')
    require(len(draft['cases'])==len(value['cases']),'materialized guard coverage differs')
    for original,case in zip(draft['cases'],value['cases']):
        require(set(original)==set(case) and all(original[k]==case[k] for k in set(case)-{'files'}),'materialized guard declaration differs')
        require(set(original['files'])==set(case['files']),'draft file closure differs')
        for key,r in original['files'].items():
            require(set(r)=={'path','sha256'} and isinstance(r['path'],str) and r['path']==f"inputs/{case['name']}/{key}.bin" and case['files'][key]=={'path':str(bundle/r['path']),'sha256':r['sha256']},'guard draft relocation differs')
    validate_cases(value,bundle,oracle)
    expected={'contract.json','draft.json','boundary_guard.py'}|{str(Path(r['path']).relative_to(bundle)) for c in value['cases'] for r in c['files'].values()}
    actual=set()
    for p in bundle.rglob('*'):
        require(not p.is_symlink(),'candidate guard bundle symlink')
        if p.is_file():actual.add(str(p.relative_to(bundle)))
        else:require(p.is_dir(),'candidate guard special file')
    require(actual==expected,'candidate guard bundle file closure differs')
    return value

def materialize(task,parent,draft_ref,source_hash,dispatch_plan):
    task,parent,bundle=context(task,parent)
    require(draft_ref['path']==str(bundle/'draft.json'),'guard draft must have canonical candidate location')
    draft=load(draft_ref,bundle)
    require(set(draft)=={'version','operator','candidate_id','original_spec','original_observation','oracle','cases'} and draft['version']==DRAFT_VERSION and draft['operator']=='group_norm' and draft['candidate_id']==parent.name,'invalid guard author draft')
    template=Path(__file__).with_name('level2_candidate_guard.py');require(pointer(template)['sha256']==REVIEWED_RUNNER_SHA,'reviewed runner template changed')
    script=bundle/'boundary_guard.py';require(not script.exists(),'candidate guard runner already materialized')
    target=bundle/'contract.json';require(not target.exists(),'candidate guard contract already materialized')
    created=[]
    try:
        shutil.copyfile(template,script);created.append(script)
        cases=[]
        for row in draft['cases']:
            cases.append({**row,'files':{key:{'path':str(bundle/ref['path']),'sha256':ref['sha256']} for key,ref in row['files'].items()}})
        value=dict(version=VERSION,operator='group_norm',candidate_id=parent.name,task=str(task),source_hash=source_hash,
            dispatch_plan=dispatch_plan,script=pointer(script),draft=draft_ref,original_spec=draft['original_spec'],original_observation=draft['original_observation'],oracle=draft['oracle'],cases=cases)
        with target.open('x') as stream:
            created.append(target);json.dump(value,stream,sort_keys=True,indent=2);stream.write('\n')
        ref=pointer(target);checked_contract(ref,oracle=True,source_hash=source_hash,dispatch_plan=dispatch_plan)
        return ref
    except BaseException:
        for path in reversed(created):path.unlink(missing_ok=True)
        raise


def resolve(task,parent,artifact=UNSET,*,source_hash=None,oracle=False):
    task,parent=Path(task),Path(parent)
    if artifact is UNSET:
        from msprof_exploration_campaign import Campaign
        ledger=task.parents[1]/'ledger'
        proposal_path=parent/'proposal.json'
        proposal=json.loads(proposal_path.read_bytes()) if proposal_path.is_file() else {}
        declared=proposal.get('artifacts',{}).get('semantic_guard_contract')
        if not ledger.exists():
            require(declared is None,'candidate guard requires registered ledger binding')
            return None
        candidates=Campaign(ledger).state['tasks'][task.name]['candidates']
        if parent.name not in candidates:
            require(declared is None,'candidate guard requires registered source')
            return None
        state=candidates[parent.name]
        artifact=state.get('artifacts',{}).get('semantic_guard_contract');source_hash=state['source_hash']
        require(artifact==declared,'candidate guard proposal/ledger artifact differs')
        if artifact is not None:
            require(state['artifacts'].get('proposal')==pointer(proposal_path),'registered guard proposal differs')
    if artifact is None:return None
    return checked_contract(artifact,oracle=oracle,source_hash=source_hash,dispatch_plan=pointer(parent/'dispatch_plan.json'))


def execution_files(root):
    """Exact private guard files; completion/closure are separately hash-bound."""
    root=Path(root)
    require(root.is_absolute() and root==root.resolve(),'guard execution root aliased')
    files=[]
    for path in sorted(root.rglob('*')):
        require(not path.is_symlink(),'guard execution symlink forbidden')
        if path.is_file():
            if path.parent==root and path.name in ('completion.json','evidence-closure.json'):continue
            files.append(pointer(path))
        else:require(path.is_dir(),'guard execution special file forbidden')
    return {'version':'level2_candidate_guard_execution_closure_v1','root':str(root),'files':files}


def checked_execution(ref,root):
    require(isinstance(ref,dict) and ref.get('path')==str(Path(root)/'evidence-closure.json'),'guard execution closure location differs')
    value=load(ref,Path(root))
    require(value==execution_files(root),'guard execution file closure or bytes differ')
    return value
