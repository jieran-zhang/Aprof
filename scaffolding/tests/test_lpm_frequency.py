"""Synthetic raw CANN 9 clock fixtures; no hardware qualification claim."""
import csv, io, json, struct
from types import SimpleNamespace
import pytest
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime import full_call_pmu as pmu


@pytest.fixture
def fixture(tmp_path):
    reader=LocalEvidence(tmp_path/'records'); files={}; root='PROF_cpu_fixture/device_0/'
    def put(name,data):
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data if isinstance(data,bytes) else data.encode())
        files[name]=reader.register_artifact(path)
    def frequency(events,kind=0):
        value=[len(events),kind]
        for tick,mhz in events:value.extend([tick,mhz,0])
        value.extend([0]*(167-len(value)))
        put(root+'data/lpmInfoConv.data.0.slice_0',struct.pack('<II'+'QII'*55,*value))
    names={role:['aprof_'+role+'_exp_kernel'] for role in pmu.ROLES}
    scope=dict(protocol=pmu.PROTOCOL,device=0,role_kernel_names=names,
        launches_per_call={r:1 for r in names},metrics={'vec_time':{'field':'aiv_vec_time(us)'}})
    row={'Op Name':names['baseline'][0],'Task Start Time(us)':'1040','Task Duration(us)':'10',
         'Task Type':'AI_VECTOR_CORE','Stream ID':'1','Task ID':'0','Device_id':'0','aiv_vec_time(us)':'3'}
    stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=list(row));writer.writeheader();writer.writerow(row)
    put('PROF_cpu_fixture/mindstudio_profiler_output/op_summary.csv',stream.getvalue())
    put(root+'info.json.0',json.dumps({'DeviceInfo':[dict(id=0,ctrl_cpu_endian_little=1,
        hwts_frequency='50',aic_frequency='1850',aiv_frequency='1850')]}))
    put(root+'dev_start.log.0','cntvct: 100000\n')
    put(root+'host_start.log.0','[Device0]\nclock_monotonic_raw: 2000000\ncntvct_diff: 0\n')
    put(root+'start_info.0',json.dumps(dict(collectionTimeBegin='1000',clockMonotonicRaw='2000000')))
    put(root+'end_info.0',json.dumps(dict(collectionTimeEnd='1100')))
    frequency([(99000,800),(100000,1850)])
    return SimpleNamespace(**locals())


def test_real_current_value_joins_full_kernel_interval(fixture):
    f=fixture;basis=pmu._frequency_basis(f.reader,f.files,f.scope,'baseline')
    assert basis[f.names['baseline'][0]]==dict(device='0',op_type='AI_VECTOR_CORE',frequencies=[1850.],
        sdk_reported_frequency=1850.,basis='raw_lpm_current_frequency_v1')
    f.frequency([(99000,800)])
    assert pmu._frequency_basis(f.reader,f.files,f.scope,'baseline')[f.names['baseline'][0]]['frequencies']==[800.]
    assert pmu.PMU_FIELDS['aiv_vec_time(us)']=='us' and pmu.PMU_FIELDS['aic_mte2_ratio']=='ratio'


@pytest.mark.parametrize('defect',['absent','voltage_only','future_only','transition','missing_clock','corrected_host'])
def test_no_supported_current_frequency_stays_unknown(fixture,defect):
    f=fixture
    if defect=='absent':del f.files[f.root+'data/lpmInfoConv.data.0.slice_0']
    elif defect=='voltage_only':f.frequency([(99000,1850)],kind=1)
    elif defect=='future_only':f.frequency([(103000,1850)])
    elif defect=='transition':f.frequency([(99000,1850),(102250,800)])
    elif defect=='missing_clock':del f.files[f.root+'dev_start.log.0']
    else:f.put(f.root+'host_start.log.0','[Device0]\nclock_monotonic_raw: 2000000\ncntvct_diff: 1\n')
    assert pmu._frequency_basis(f.reader,f.files,f.scope,'baseline') is None


@pytest.mark.parametrize('defect',['truncated','zero','contradictory','out_of_window','wrong_device'])
def test_malformed_or_unbound_clock_is_rejected(fixture,defect):
    f=fixture
    if defect=='truncated':f.put(f.root+'data/lpmInfoConv.data.0.slice_0',b'incomplete')
    elif defect=='zero':f.frequency([(99000,0)])
    elif defect=='contradictory':f.frequency([(99000,1850),(99000,800)])
    elif defect=='out_of_window':f.put(f.root+'end_info.0',json.dumps(dict(collectionTimeEnd='1045')))
    else:f.put(f.root+'host_start.log.0','[Device1]\nclock_monotonic_raw: 2000000\ncntvct_diff: 0\n')
    with pytest.raises(ValueError):pmu._frequency_basis(f.reader,f.files,f.scope,'baseline')
