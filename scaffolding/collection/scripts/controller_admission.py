"""Record a controller's actual stages against a predeclared timing protocol."""
from __future__ import annotations

import json
from pathlib import Path
import time

from run_aprof_job import dump
from validation_operator_adapter import timing_config
from timing_admission import (control_statistics, verify_timing_admission,
                              verify_capture_window, verify_profile_window)


class AdmissionRecorder:
    def __init__(self, api, store, output, plan, sources, binaries, prepared, source_hashes,
                 run_id, candidate_id, purpose, *, profile_kernel=None):
        self.api, self.store, self.output = api, store, output
        self.events, self.collected, self.partial = [], {}, {}
        self.active = None
        self.expected = dict(run_id=run_id, candidate_id=candidate_id, operator=plan["operator"],
                             source_hashes=source_hashes, purpose=purpose)
        if profile_kernel is not None and profile_kernel not in plan["profile"]["kernels"]:
            raise ValueError("controller profile kernel is outside the frozen task choices")
        self.configs, inputs, oracles = {}, {}, {}
        for phase in ("aa_before", "formal", "aa_after"):
            aa = phase.startswith("aa_")
            config = timing_config(plan["operator"],
                {role: sources["baseline"] if aa else sources[role] for role in ("baseline", "candidate")},
                {role: binaries["baseline"] if aa else binaries[role] for role in ("baseline", "candidate")},
                prepared, output / (phase + "-config"), repeat=plan["repeat"],
                physical_device=plan["physical_device"],
                case_ids=plan["control_case_ids"] if aa else list(range(1, 21)))
            config = api["timing"].config_value(config)
            self.configs[phase] = config
            for case in config["cases"]:
                for path in case["prepared_files"]:
                    if path not in inputs:
                        inputs[path] = store.register_artifact(path)
                for epoch in case["epochs"]:
                    for role in ("baseline", "candidate"):
                        argv = epoch[role]["verify_command"]
                        for path in (argv[0], argv[1]):
                            if path not in oracles:
                                oracles[path] = store.register_artifact(path)
        for source in sources.values():
            generator = source / "scripts/gen_data.py"
            oracles[str(generator)] = store.register_artifact(generator)
        self.protocol = dict(schema_version=1, **{k: v for k, v in self.expected.items() if k != "purpose"},
            purpose=purpose, created_at=time.time(), measurement_policy={"repeat": plan["repeat"]},
            profile_scope={"case_id": plan["profile"]["case_id"],
                           "kernels": [profile_kernel] if profile_kernel is not None else plan["profile"]["kernels"]},
            binary_hashes={role: store.register_artifact(path) for role, path in binaries.items()},
            collector_ref=store.register_artifact(api["timing"].__file__),
            phases={phase: {"config_ref": self.save(phase + "-frozen-config.json", config)} for phase, config in self.configs.items()},
            input_inventory_ref=self.save("timing-input-inventory.json", inputs), oracle_files=oracles)
        self.protocol_ref = self.save("protocol.json", self.protocol)
        self.registration = dict(schema_version=1, run_id=run_id, candidate_id=candidate_id,
            protocol_ref=self.protocol_ref, created_at=time.time(), max_attempts=1, stop_on_failure=True,
            resampling="none", stages=["correctness", "aa_before", "formal", "aa_after", "profile"])
        self.registration_ref = self.save("registration.json", self.registration)
        self.expected["registration_ref"] = self.registration_ref
        self.save_roster()

    def save(self, name, value):
        path = self.output / name
        dump(path, value)
        return self.store.register_artifact(path)

    def save_roster(self):
        self.roster_ref = self.save("attempt-roster.json", dict(schema_version=1,
            registration_ref=self.registration_ref, events=self.events))

    def event(self, stage, state, evidence=(), exit_status=None):
        sequence = len(self.events)
        expected_stage = self.registration["stages"][sequence // 2]
        expected_state = "started" if sequence % 2 == 0 else "completed"
        if stage != expected_stage or state != expected_state:
            raise ValueError("controller attempted an unregistered or repeated stage")
        event = dict(sequence=sequence, previous_ref=self.events[-1] if self.events else self.registration_ref,
            registration_ref=self.registration_ref, stage=stage, state=state, at=time.time(), evidence_refs=list(evidence))
        if state == "completed":
            event["exit_status"] = exit_status
        self.events.append(self.save(f"stage-events/{sequence:02d}.json", event))
        self.active = stage if state == "started" else None
        self.save_roster()

    def start(self, stage):
        self.event(stage, "started")

    def complete(self, stage, evidence, *, passed=True):
        self.event(stage, "completed", evidence, 0 if passed else 1)

    def register_raw_dependencies(self, raw):
        for execution in raw.get("case_executions", []):
            for epoch in execution.get("epochs", []):
                for record in (*epoch.get("commands", {}).values(), *epoch.get("verifications", {}).values()):
                    path = record.get("log_path")
                    if path and Path(path).is_file():
                        self.store.register_artifact(path)
                for path in epoch.get("output_hashes", {}):
                    if Path(path).is_file():
                        self.store.register_artifact(path)

    def collect(self, phase):
        self.start(phase)
        directory = self.output / phase
        try:
            report = self.api["timing"].collect(self.configs[phase], directory)
        finally:
            # Collector failures still retain their actual partial stdout/output
            # and samples. A failed stage never receives a successful event.
            partial = []
            path = directory / "raw_measurements.json"
            if path.is_file():
                self.register_raw_dependencies(json.loads(path.read_text()))
            for name in ("raw_measurements.json", "config.json", "measurement_report.json"):
                path = directory / name
                if path.is_file():
                    partial.append(self.store.register_artifact(path))
            self.partial[phase] = partial
        raw = json.loads((directory / "raw_measurements.json").read_text())
        self.register_raw_dependencies(raw)
        pointers = dict(raw_ref=self.store.register_artifact(directory / "raw_measurements.json"),
            config_ref=self.protocol["phases"][phase]["config_ref"],
            report_ref=self.store.register_artifact(directory / "measurement_report.json"))
        self.collected[phase] = pointers
        result = {"passed": bool(report["stable"])}
        if phase.startswith("aa_") or self.protocol["purpose"] == "baseline_qualification":
            before = None
            if phase == "aa_after":
                before = json.loads(self.store.verify_artifact(self.collected["aa_before"]["raw_ref"]).read_text())
            result = control_statistics(raw, self.configs[phase], before_raw=before)
            if not report["stable"]:
                result.update(passed=False, reason="formal measurement stability failed")
        verdict = self.save(phase + "-admission.json", result)
        self.complete(phase, [*pointers.values(), verdict], passed=result["passed"])
        if not result["passed"]:
            raise RuntimeError(f"{phase} measurement control failed; no resampling: {result.get('reason', '')}")
        return report

    def fail_active(self, error):
        if self.active:
            ref = self.save("stage-failure.json", {"type": type(error).__name__, "message": str(error)})
            self.complete(self.active, [ref, *self.partial.get(self.active, [])], passed=False)

    def finish(self, *, capture_refs=(), mechanism_report_ref=None):
        report = dict(schema_version=1, **{k: v for k, v in self.expected.items() if k not in ("purpose", "registration_ref")},
            protocol_ref=self.protocol_ref, registration_ref=self.registration_ref,
            attempt_roster_ref=self.roster_ref, **self.collected)
        reference = self.save("control-report.json", report)
        verdict = verify_timing_admission(self.store, reference, expected=self.expected)
        for capture in capture_refs:
            verify_capture_window(self.store, capture, window=verdict["stage_windows"]["profile"],
                                  control_report_ref=reference, role="baseline")
        if mechanism_report_ref:
            verify_profile_window(self.store, mechanism_report_ref, window=verdict["stage_windows"]["profile"],
                                  control_report_ref=reference)
        self.save("control-replay.json", verdict)
        return {"control_report": reference, "qualification_registration": self.registration_ref}
