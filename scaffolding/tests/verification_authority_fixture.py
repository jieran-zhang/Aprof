"""Synthetic prior ledger records for transport-only tests; no campaign mutation."""
import json
from pathlib import Path
import hashlib

def packed(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def sha(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
def save(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,sort_keys=True)+'\n')
def reference(path):return {'path':str(path),'sha256':sha(path.read_bytes())}
def anchor(task,cohort,kind='calibration',cid=None):
    ledger=task.parents[1]/'ledger';stage=cohort.parent;report=json.loads((cohort/'report.json').read_text())
    report['operator']=task.name;report['comparison_kind']='aa' if kind=='calibration' else 'ab'
    existing={row['directory'] for row in report['sessions']}
    for directory in json.loads((cohort/'group-completion.json').read_text())['completed_sessions']:
        if directory not in existing:report['sessions'].append({'directory':directory,'artifacts':{}})
    for row in report['sessions']:
        for name in ('validation.json','bindings.json','completion.json','msprof.execution.json','native/journal.jsonl'):
            path=Path(row['directory'])/name
            if path.exists():row['artifacts'][str(path)]=sha(path.read_bytes())
    save(cohort/'report.json',report)
    config={'schema_version':'msprof_exploration_campaign_v2','tasks':{task.name:{'split':task.parents[1].name}}}
    save(ledger/'config.json',config);confighash=sha(packed(config));save(ledger/'config.sha256.json',{'sha256':confighash})
    rows=[]
    def event(op,args):
        row={'sequence':len(rows),'event_id':'genesis' if not rows else 'event-'+str(len(rows)),'operation':op,'arguments':args,'recorded_at':'2026-10-06T00:00:00Z','previous_hash':rows[-1]['hash'] if rows else 'sha256:'+'0'*64,'config_hash':confighash}
        row['hash']=sha(packed(row));rows.append(row)
    event('prepare',{});source='sha256:'+'1'*64;cid=cid or task.name+'001'
    event('register',{'workload':task.name,'candidate_id':cid,'source_hash':source})
    owncid=None if kind=='calibration' else cid;sid=('baseline' if owncid is None else owncid)+'-'+stage.name
    event('start',{'workload':task.name,'candidate_id':owncid,'stage_id':sid,'kind':'control' if kind=='calibration' else 'timing','plan':json.loads((stage/'stage-plan.json').read_text())})
    event('finish',{'workload':task.name,'stage_id':sid,'outcome':'success','native_started':True,'evidence':{'result':reference(stage/'result.json')}})
    if kind=='calibration':event('start',{'workload':task.name,'candidate_id':cid,'stage_id':cid+'-search','kind':'timing','plan':{'calibration_report':reference(cohort/'report.json')}})
    else:
        feedback={'version':'level2_source_feedback_v1','operator':task.name,'candidate_id':cid,'source_hash':source,'status':'measured','stages':[{'stage_id':sid,'status':'passed','result':reference(stage/'result.json')}],'comparisons':[{'relation':cohort.name,'report':reference(cohort/'report.json')}]}
        feedbackhash=sha((json.dumps(feedback,ensure_ascii=False,sort_keys=True)+'\n').encode())
        event('observe',{'workload':task.name,'candidate_id':cid,'observation_id':cid+'-feedback-01','close_feedback':True,'stage_ids':[sid],'feedback':feedback,'report_ref':feedbackhash})
    (ledger/'events.jsonl').write_bytes(b''.join(packed(row)+b'\n' for row in rows))
    return ledger,rows


def legacy_archive(store,session,destination,retire=False):
    """Write a literal historical v1 transport fixture, without running old code."""
    import io,tarfile,stat
    destination.mkdir();(destination/'dedup.lock').touch();root=session/'verification';facts,_=store.closed_from_reader(session,store.raw_read)
    rows=[];buffer=io.BytesIO()
    with tarfile.open(fileobj=buffer,mode='w',format=tarfile.USTAR_FORMAT) as tar:
        for path in sorted(p for p in root.rglob('*') if p.is_file()):
            data=path.read_bytes();st=path.stat();relative=path.relative_to(root).as_posix()
            row={'path':str(path),'relative_path':relative,'sha256':sha(data),'size_bytes':len(data),'mode':stat.S_IMODE(st.st_mode),'uid':st.st_uid,'gid':st.st_gid,'mtime_ns':st.st_mtime_ns};rows.append(row)
            info=tarfile.TarInfo(relative);info.size=len(data);info.mode=row['mode'];info.uid=st.st_uid;info.gid=st.st_gid;info.mtime=st.st_mtime_ns//1000000000;tar.addfile(info,io.BytesIO(data))
    (destination/'verification.tar').write_bytes(buffer.getvalue());(destination/'producer.py').write_bytes(b'# Inert synthetic historical producer snapshot.\n')
    seal={'version':store.VERSION,'session':str(session),'logical_root':str(root),'closed_evidence':facts,'archive':reference(destination/'verification.tar'),'producer':reference(destination/'producer.py'),'members':rows,'source_bytes_preserved':True}
    save(destination/'seal.json',seal)
    if retire:
        for row in rows:Path(row['path']).unlink()
        for directory in root.iterdir():directory.rmdir()
        root.rmdir();save(destination/'compacted.json',{'version':store.VERSION,'status':'complete','seal':reference(destination/'seal.json'),'source_bytes_preserved':True})
    return seal
