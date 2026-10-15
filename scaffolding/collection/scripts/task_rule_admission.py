"""Replay the outer stage chain and real exit of one registered Task rule trial.

This is one structural check, not optimization or publication admission. The
caller still replays correctness, boundary, screen, Task and mechanism evidence,
and checks every attempt against the campaign anchor. No experiment is executed.
"""
from task_budget import teacher_budget, rule_execution_job, collection_policy
from datetime import datetime
from pathlib import Path

from timing_admission import ReplayCache, checked_path, identity, number, read, require


PROTOCOL = "rule_task_admission_v1"
TASK_PROTOCOL = "shared_buffer_msprof_task_window_v5"
STAGES = ("correctness", "boundary", "screen", "task_measurement", "profile", "online_admission")
IDENTITY = ("run_id", "candidate_id", "operator", "source_hashes")


def _timestamp(value):
    require(isinstance(value, str), "execution timestamp must be an actual ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(parsed.tzinfo is not None, "execution timestamp lacks timezone")
        return number(parsed.timestamp())
    except (TypeError, ValueError) as error:
        raise ValueError("invalid execution timestamp") from error


def verify_task_attempt_roster(store, report_ref, *, expected):
    """Bind the post-build stage protocol to its pre-launch plan and actual job.

    The pre-launch anchor fixes sources, input/oracle plans, job and total budget.
    The derived protocol may add the actual binary and Task/profile configs after
    the single build; it cannot change the anchor's plan references or budget.
    """
    store = store if isinstance(store, ReplayCache) else ReplayCache(store)
    require(set(expected) == {*IDENTITY, "anchor_ref", "protocol_ref",
                              "qualification_registration_ref", "execution_ref"},
            "outer replay requires trusted plan identities and the dispatcher execution receipt")
    report = read(store, report_ref)
    identity(report, expected)
    require(report.get("schema_version") == 1 and report.get("protocol") == PROTOCOL,
            "unsupported Task outer report")
    for key in ("anchor_ref", "protocol_ref", "qualification_registration_ref", "execution_ref"):
        require(report.get(key) == expected[key], "Task outer " + key + " differs")
    anchor = read(store, expected["anchor_ref"])
    protocol = read(store, expected["protocol_ref"])
    registration = read(store, expected["qualification_registration_ref"])
    for value in (anchor, protocol):
        identity(value, expected)
        require(value.get("schema_version") == 1 and value.get("protocol") == PROTOCOL
                and value.get("task_protocol") == TASK_PROTOCOL
                and value.get("purpose") == "promotion", "wrong Task rule protocol/purpose")
    require(expected["operator"] in {"exp", "sigmoid"}, "unregistered rule operator")
    require(protocol.get("anchor_ref") == expected["anchor_ref"], "derived protocol lost its anchor")
    plan_keys = ("job_ref", "budget_seconds", "input_inventory_ref", "boundary_plan_ref",
                 "screen_plan_ref", "profile_plan_ref", "source_review_ref", "history_refs")
    require(all(key in anchor and protocol.get(key) == anchor[key] for key in plan_keys),
            "derived protocol changed the frozen trial plan")
    require(isinstance(anchor["history_refs"], list) and anchor["history_refs"]
            and len(anchor["history_refs"]) == len(set(anchor["history_refs"])),
            "prior failure references are missing or duplicated")
    for key in plan_keys:
        if key.endswith("_ref"):
            store.verify_artifact(anchor[key])
    for ref in anchor["history_refs"]:
        store.verify_artifact(ref)
    budget = teacher_budget(lambda ref: read(store, ref), anchor)
    require(collection_policy(protocol)==collection_policy(anchor), "derived protocol changed frozen stop policy")
    require(registration.get("schema_version") == 1
            and registration.get("protocol_ref") == expected["protocol_ref"]
            and registration.get("anchor_ref") == expected["anchor_ref"]
            and all(registration.get(key) == expected[key] for key in ("run_id", "candidate_id"))
            and registration.get("max_attempts") == 1
            and registration.get("stop_on_failure") is True
            and registration.get("resampling") == "none"
            and registration.get("stages") == list(STAGES),
            "Task rule requires one registered attempt with the complete stage order")

    job = read(store, anchor["job_ref"])
    checked_path(store, Path(job["output_dir"]) / "execution.json", expected["execution_ref"])
    execution = read(store, report["execution_ref"])
    launch = read(store, protocol["dispatcher_launch_ref"]) if "dispatcher_launch_ref" in protocol else None
    actual_job = rule_execution_job(lambda ref: read(store, ref), anchor, job, launch)
    require(execution.get("kind") == "aprof_execution_report"
            and execution.get("schema_version") == "1.0.0"
            and execution.get("job") == actual_job
            and execution.get("status") == "passed" and execution.get("exit_code") == 0
            and not execution.get("error"), "actual rule process did not exit successfully")
    require(number(job["timeout_seconds"]) == budget
            and 0 < number(execution["duration_seconds"]) <= actual_job["timeout_seconds"],
            "actual whole-job duration exceeds the registered budget")
    started, finished = (_timestamp(execution[key]) for key in ("started_at", "finished_at"))
    require(started <= finished and finished - started <= actual_job["timeout_seconds"],
            "actual whole-job wall interval exceeds its budget")
    if launch is not None and launch["schema_version"] == 2:
        require(launch["started_at"] <= started <= finished <= launch["started_at"] + budget,
                "rule execution escaped the original parent window")
    require(number(anchor["created_at"]) <= started <= number(protocol["created_at"])
            <= number(registration["created_at"]) <= finished,
            "trial plan/build binding was not frozen in order")
    for key in ("stdout", "stderr"):
        pointer = execution[key]
        require(set(pointer) == {"path", "sha256"}, "actual job log pointer differs")
        checked_path(store, pointer["path"], pointer["sha256"])

    roster = read(store, report["attempt_roster_ref"])
    require(roster.get("schema_version") == 1
            and roster.get("registration_ref") == expected["qualification_registration_ref"]
            and isinstance(roster.get("events"), list) and len(roster["events"]) == 2 * len(STAGES),
            "Task attempt roster is incomplete")
    evidence = report.get("stage_evidence")
    require(isinstance(evidence, dict) and set(evidence) == set(STAGES)
            and all(isinstance(refs, list) and refs and len(refs) == len(set(refs))
                    for refs in evidence.values()), "Task stage evidence inventory differs")
    previous = expected["qualification_registration_ref"]
    clock = number(registration["created_at"])
    windows = {}
    for sequence, ref in enumerate(roster["events"]):
        event = read(store, ref)
        stage, state = STAGES[sequence // 2], ("started", "completed")[sequence % 2]
        current = number(event["at"])
        require(event.get("sequence") == sequence and event.get("previous_ref") == previous
                and event.get("registration_ref") == expected["qualification_registration_ref"]
                and event.get("stage") == stage and event.get("state") == state
                and clock <= current <= finished, "Task stage chain/order/actual exit differs")
        if state == "started":
            require(not event.get("evidence_refs") and event.get("exit_status") is None,
                    "started stage already claims completion evidence")
            windows[stage] = [current]
        else:
            require(event.get("exit_status") == 0 and event.get("evidence_refs") == evidence[stage],
                    "Task stage failed or omitted/substituted evidence")
            for item in evidence[stage]:
                store.verify_artifact(item)
            windows[stage].append(current)
        previous, clock = ref, current
    if collection_policy(anchor) is not None:
        _verify_screen_unit(store, report, evidence["screen"], windows["screen"], launch, collection_policy(anchor))
        _verify_profile_units(store, report, evidence["profile"], windows["profile"], launch, collection_policy(anchor))
    return {"valid": True, "scope": "task_attempt_roster_and_actual_exit",
            "admission_authority": False, "protocol_ref": expected["protocol_ref"],
            "qualification_registration_ref": expected["qualification_registration_ref"],
            "stage_windows": windows, "stage_evidence": evidence,
            "execution_ref": report["execution_ref"], "budget_seconds": budget,
            "actual_duration_seconds": execution["duration_seconds"]}


def _verify_screen_unit(store, report, evidence, window, launch, policy):
    """Bind the complete screen to one task unit; full raw/statistical replay stays mandatory."""
    from aprof_runtime.task_window_measurement_admission import replay_collection_unit
    from screen_parser import CASES
    require(launch is not None and launch['schema_version'] == 2 and len(evidence) == 2
            and evidence[0] == report['screen_report_ref'], 'whole screen unit receipt missing')
    unit = replay_collection_unit(store, evidence[1],
        parent_deadline=launch['monotonic_deadline'], policy=policy, kind='task')
    result = read(store, report['screen_report_ref'])
    upper = min(window[1], unit['wall_deadline'])
    require(launch['started_monotonic'] <= unit['started_monotonic'] < launch['monotonic_deadline']
            and window[0] <= unit['started_at'] <= number(result['started_at'])
            <= number(result['finished_at']) <= upper,
            'whole screen escaped its original collection unit')
    require([row['case_id'] for row in result['sessions']] == CASES[report['operator']],
            'whole screen unit omitted or reordered a fixed case')
    previous = result['started_at']
    for session in result['sessions']:
        require(previous <= number(session['started_at']) <= number(session['finished_at'])
                <= result['finished_at'] and set(session['oracles']) == {'baseline', 'candidate'},
                'screen unit session order or oracle scope differs')
        clock = session['started_at']
        for embedded in (session['capture'], session['export'],
                         session['oracles']['baseline'], session['oracles']['candidate']):
            execution = read(store, embedded['log_hash'])
            require({k: v for k, v in embedded.items() if k != 'result_ref'} ==
                    dict(execution, log_hash=embedded['log_hash']), 'screen unit actual execution differs')
            require(execution['exit_code'] == 0 and not execution.get('error')
                    and clock <= number(execution['started_at']) <= number(execution['ended_at'])
                    <= session['finished_at']
                    and 0 < number(execution['timeout_seconds']) <= unit['wall_deadline'] - execution['started_at'] + .01
                    and execution['ended_at'] - execution['started_at'] <= execution['timeout_seconds'],
                    'screen execution escaped its original unit')
            clock = execution['ended_at']
        previous = session['finished_at']


def _verify_profile_units(store, report, evidence, window, launch, policy):
    """New reserve plans bind each complete original PMU role to its unit window."""
    from aprof_runtime.task_window_measurement_admission import replay_collection_unit
    from task_profile_admission import _verify_capture_executions
    require(launch is not None and launch['schema_version']==2 and len(evidence)==4
            and evidence[0]==report['mechanism_report_ref'], 'complete role unit receipts missing')
    mechanism=read(store,report['mechanism_report_ref'])
    previous=window[0]
    for role,reference in zip(('baseline','candidate'),evidence[2:],strict=True):
        sealed=read(store,reference)
        require(set(sealed)=={'kind','role','profile_ref','oracle_ref','collection_unit_ref','finished_at'}
                and sealed['kind']=='complete_role_collection_v1' and sealed['role']==role,
                'complete role unit identity differs')
        require({metric[role+'_profile_hash'] for metric in mechanism['metrics']}=={sealed['profile_ref']},
                'role unit profile differs from gate evidence')
        profile=read(store,sealed['profile_ref'])
        manifest=read(store,profile['capture_manifest_hash'])
        unit=replay_collection_unit(store,sealed['collection_unit_ref'],
            parent_deadline=launch['monotonic_deadline'],policy=policy,kind='pmu')
        upper=min(window[1],unit['wall_deadline'])
        require(manifest['role']==role and previous<=unit['started_at']<=upper
                and launch['started_monotonic']<=unit['started_monotonic']<launch['monotonic_deadline'],
                'role collection unit reordered or outside original task')
        _verify_capture_executions(store,manifest,[unit['started_at'],upper])
        executions=[read(store,row['log_hash']) for row in manifest['warmup_runs']]
        for row in manifest['captures']:
            capture=read(store,row['log_hash'])
            executions.extend(capture[key] for key in ('capture','import') if key in capture)
        require(all(0<number(item['timeout_seconds'])<=unit['wall_deadline']-item['started_at']+.01
                and item['ended_at']-item['started_at']<=item['timeout_seconds'] for item in executions),
                'role capture timeout escaped its original unit')
        last=read(store,manifest['captures'][-1]['log_hash'])
        capture_finished=max(number(last[key]['ended_at']) for key in ('capture','import') if key in last)
        oracle=read(store,sealed['oracle_ref'])
        require(oracle['exit_code']==0 and not oracle.get('error')
                and capture_finished<=number(oracle['started_at'])<=number(oracle['ended_at'])
                <=number(sealed['finished_at'])<=upper
                and 0<number(oracle['timeout_seconds'])<=unit['wall_deadline']-oracle['started_at']+.01
                and oracle['ended_at']-oracle['started_at']<=oracle['timeout_seconds'],
                'complete role oracle escaped its original unit')
        for key in ('stdout_hash','stderr_hash'): store.verify_artifact(oracle[key])
        previous=sealed['finished_at']
