#!/usr/bin/env python3
"""Reviewed GN guard revision runner; all values come from a bound contract."""
from pathlib import Path
import argparse,json,sys,shutil

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--repository',type=Path,required=True)
    parser.add_argument('--contract',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--verify',action='store_true')
    args=parser.parse_args()
    sys.path[:0]=[str(args.repository/'scripts'),str(args.repository/'src')]
    from level2_guard_contract import checked_contract,pointer,compare,read_array,selection
    contract=checked_contract(pointer(args.contract),oracle=False)
    if contract['dispatch_plan']!=pointer(args.plan):raise ValueError('guard dispatch differs')
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    commands=[];results=[]
    for case in contract['cases']:
        dest=out/case['name'];dest.mkdir(exist_ok=True)
        for key,ref in case['files'].items():
            target=dest/(key+'.bin')
            if target.exists():
                if pointer(target)['sha256']!=ref['sha256']:raise ValueError('existing private input differs')
            else:shutil.copyfile(ref['path'],target)
        selected,metadata=selection(contract,case)
        shape=metadata['shape'];attrs=metadata['attributes'];dtype=metadata['dtype']
        argv=['--shape',','.join(map(str,shape)),'--dtype',dtype,'--groups',str(attrs['num_groups']),
              '--epsilon',str(attrs['epsilon']),'--x',str(dest/'x.bin'),'--gamma',str(dest/'gamma.bin'),
              '--beta',str(dest/'beta.bin'),'--output',str(dest/'output.bin'),'--device','0']
        commands.append(dict(name=case['name'],argv=argv,expected_key=selected['tiling_key'],
            expected_entry=selected['kernel_entry'],reference=str(dest/'expected.bin'),metadata=metadata))
        result=dict(name=case['name'],dispatch=selected,reference_status='original_oracle_bytes_bound_before_native',
            oracle=contract['oracle'],status='cpu_reference_prepared_not_hardware_verified')
        if args.verify:
            if (dest/'output.bin').stat().st_size != (dest/'expected.bin').stat().st_size:
                raise ValueError('guard output byte size differs from bound reference')
            result['output']=compare(read_array(dest/'output.bin',dtype),read_array(dest/'expected.bin',dtype),dtype)
            result['passed']=result['output']['passed']
            result['status']='coordinator_output_verified' if result['passed'] else 'coordinator_output_failed'
        results.append(result)
    (out/'coordinator_commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    value=dict(operator='group_norm',hardware_executed_by_this_script=False,results=results)
    (out/('verification.json' if args.verify else 'cpu_preparation.json')).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(operator='group_norm',cases=len(results),mode='verify_existing_outputs' if args.verify else 'cpu_only',passed=all(r.get('passed',True) for r in results))))
    if any(not r.get('passed',True) for r in results):raise SystemExit(1)

if __name__=='__main__':main()
