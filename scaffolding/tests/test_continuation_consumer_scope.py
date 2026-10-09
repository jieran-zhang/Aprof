"""Cross-task engineering scope regression: temporary files only."""
from test_continuation_consumers import continuation, collector, certified_closed

def test_engineering_other_task_manifests_do_not_enter_archive_owner_scope(tmp_path,monkeypatch):
    import test_continuation_product as fixture
    data=b'tiny source archive identity'
    monkeypatch.setattr(continuation,'SOURCE',continuation.sha(data))
    real_put=fixture.put;foreign=tmp_path/'run/train/tasks/gcd/manifest.json'
    foreign_ref=real_put(foreign,{'fixture':'unrelated task'})
    def expanded(path,value):
        if isinstance(value,dict) and value.get('version')=='level2_frozen_engineering_v1':
            value={**value,'task_manifests':[*value['task_manifests'],foreign_ref]}
        return real_put(path,value)
    monkeypatch.setattr(fixture,'put',expanded)
    f=fixture.certified(tmp_path);(f['child']/'source.tar').write_bytes(data);fixture.close(f)
    foreign.unlink()  # Its bytes are irrelevant to this operator's authority.
    p=continuation.resolve(f['cohort'],require_closed=True)
    assert str(foreign) not in {r['path'] for r in p['protected']}
    a=collector(f['run']);a._retain_continuation_refs(p,'dynamic_quant')
    assert str(foreign) not in {r['path'] for r in a.artifacts.values()}


def test_real_archive_closure_survives_missing_original_external_metadata(certified_closed):
    from pathlib import Path
    f=certified_closed
    p=continuation.resolve(f['cohort'],require_closed=True)
    certificate=f['certificate'];terminal=continuation.load(Path(certificate['terminal_receipt']['path']).read_bytes())
    absent=[certificate['terminal_receipt'],terminal['forensics'],terminal['health_after']]
    for ref in absent:Path(ref['path']).unlink()
    replay=continuation.resolve(f['cohort'],require_closed=True)
    assert replay==p
    a=collector(f['run']);a._retain_continuation_refs(replay,'dynamic_quant')
    indexed={ref['path'] for ref in a.artifacts.values()}
    protected={ref['path'] for ref in replay['protected']}
    assert protected<=indexed
    assert all(ref['path'] not in indexed for ref in absent)
    assert sum(path.endswith('/original-native.tar') or path.endswith('/original-scratch.tar') for path in indexed)==2
    assert any('/failed-search-p03-preservation-01/inputs/' in path for path in indexed)
