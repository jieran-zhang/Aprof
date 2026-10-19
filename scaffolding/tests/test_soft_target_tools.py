import json
import sys
from pathlib import Path

from task_controller import run_commands
from cost_breakdown import union_seconds


def test_cost_union_does_not_add_children():
    assert union_seconds([{'started_monotonic':0,'finished_monotonic':10},
        {'started_monotonic':2,'finished_monotonic':4},
        {'started_monotonic':9,'finished_monotonic':12}])==12


def test_controller_continues_independent_work_after_failure_and_target(tmp_path):
    package=Path(__file__).resolve().parents[2]/'skill-libs/graph-base/1.2.0'
    def item(name,code,**rest):return {'id':name,'argv':[sys.executable,'-c',code],
        'cwd':str(tmp_path),'target_seconds':.01,**rest}
    results=run_commands(package,tmp_path,[item('slow','import time;time.sleep(.04)'),
        item('bad','raise SystemExit(7)'),item('dependent','print("wrong")',depends_on=['bad']),
        item('report','print("retained failure")')],target=.02)
    assert [r['status'] for r in results.values()]==['passed','failed','not_evaluated','passed']
    assert not (tmp_path/'commands/dependent').exists()
    assert json.loads((tmp_path/'controller-results.json').read_text())['budget_warnings']
