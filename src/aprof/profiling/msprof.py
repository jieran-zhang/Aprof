from __future__ import annotations

import csv
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from aprof.core.models import CodeHotspot, ExperimentMetadata, Observation, TimeWindow


COMPONENT_ALIASES = {
    "vector": "vector",
    "veccore": "vector",
    "vec": "vector",
    "aivector": "vector",
    "aiv": "vector",
    "cube": "cube",
    "aicube": "cube",
    "scalar": "scalar",
    "flowctrl": "scalar",
    "flowcontrol": "scalar",
    "control": "scalar",
    "mte2": "mte2",
    "mte3": "mte3",
    "mte1": "mte1",
    "memory": "gm",
    "gm": "gm",
    "idle": "idle",
    "sync": "idle",
}


def normalize_component(value: str) -> str:
    token = value.strip().lower().replace("_", "").replace("-", "")
    for key, component in COMPONENT_ALIASES.items():
        if key in token:
            return component
    return value.strip().lower() or "unknown"


def parse_msprof_simulator(input_path: str | Path) -> Observation:
    root = Path(input_path)
    if not root.exists():
        raise FileNotFoundError(f"input path does not exist: {root}")

    run_root = _resolve_run_root(root)
    stdout_summary = _parse_msprof_stdout_summary(root, run_root)
    metadata = _load_metadata(root, run_root, stdout_summary)
    trace_path = _find_trace(run_root)
    windows = _parse_trace(trace_path) if trace_path else []
    hotspots = _parse_hotspots(run_root)

    if not windows:
        windows = _windows_from_hotspots(hotspots)
    if not windows:
        windows = _windows_from_stdout_summary(stdout_summary)

    return Observation(
        metadata=metadata,
        windows=windows,
        hotspots=hotspots,
        input_path=str(run_root),
        artifacts=_summarize_artifacts(root, run_root, trace_path, stdout_summary),
    )


def summarize_msprof_artifacts(input_path: str | Path) -> Dict[str, Any]:
    root = Path(input_path)
    if not root.exists():
        raise FileNotFoundError(f"input path does not exist: {root}")
    run_root = _resolve_run_root(root)
    stdout_summary = _parse_msprof_stdout_summary(root, run_root)
    return _summarize_artifacts(root, run_root, _find_trace(run_root), stdout_summary)


def _resolve_run_root(root: Path) -> Path:
    if (root / "trace.json").exists() or (root / "simulator").exists():
        return root
    matches = sorted(
        [path for path in root.rglob("OPPROF_*") if path.is_dir()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return matches[0] if matches else root


def _load_metadata(
    requested_root: Path, run_root: Path, stdout_summary: Optional[Dict[str, Any]] = None
) -> ExperimentMetadata:
    raw: Dict[str, Any] = {}
    for metadata_path in [
        requested_root / "metadata.json",
        run_root / "metadata.json",
        requested_root / "aprof_metadata.json",
        run_root / "aprof_metadata.json",
    ]:
        if metadata_path.exists():
            raw.update(json.loads(metadata_path.read_text(encoding="utf-8")))

    total_duration_us = float(raw.get("total_duration_us", 0.0))
    if total_duration_us == 0.0 and stdout_summary:
        total_duration_us = float(stdout_summary.get("model_run_time_us") or 0.0)

    return ExperimentMetadata(
        operator_name=str(raw.get("operator_name", run_root.name)),
        kernel_version=str(raw.get("kernel_version", "unknown")),
        shape=str(raw.get("shape", "unknown")),
        data_type=str(raw.get("data_type", "unknown")),
        soc_version=str(raw.get("soc_version", "unknown")),
        total_duration_us=total_duration_us,
        total_ops=float(raw.get("total_ops", 0.0)),
        total_bytes=float(raw.get("total_bytes", 0.0)),
        notes=str(raw.get("notes", "")),
    )


def _find_trace(root: Path) -> Optional[Path]:
    candidates = [root / "trace.json", root / "simulator" / "trace.json"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    matches = sorted(root.rglob("trace.json"))
    return matches[0] if matches else None


def _parse_trace(trace_path: Path) -> List[TimeWindow]:
    raw = json.loads(trace_path.read_text(encoding="utf-8"))
    events = raw.get("traceEvents", raw if isinstance(raw, list) else [])
    windows: List[TimeWindow] = []

    for event in events:
        if not isinstance(event, dict) or event.get("ph", "X") != "X":
            continue
        args = event.get("args") or {}
        name = str(event.get("name", "unknown"))
        component = normalize_component(
            str(
                args.get("component")
                or args.get("pipeline")
                or args.get("unit")
                or name
                or event.get("cat")
            )
        )
        start_us = _float_field(event, ["ts", "start_us", "startTime"], 0.0)
        duration_us = _float_field(event, ["dur", "duration_us", "duration"], 0.0)
        windows.append(
            TimeWindow(
                index=len(windows),
                start_us=start_us,
                end_us=start_us + duration_us,
                component=component,
                name=name,
                cycles=_float_field(args, ["cycles", "cycle", "Cycle"], 0.0),
                ops=_float_field(args, ["ops", "operation", "operations"], 0.0),
                bytes_moved=_float_field(
                    args,
                    ["bytes", "bytes_moved", "Bytes", "memory_bytes", "size"],
                    0.0,
                ),
                source=str(trace_path),
                raw=event,
            )
        )

    return sorted(windows, key=lambda item: (item.start_us, item.end_us, item.index))


def _parse_hotspots(root: Path) -> List[CodeHotspot]:
    hotspots: List[CodeHotspot] = []
    for csv_path in sorted(root.rglob("*_code_exe.csv")):
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                code = _str_field(row, ["code", "Code", "source", "Source", "func_name"])
                if not code:
                    continue
                hotspots.append(
                    CodeHotspot(
                        code=code,
                        call_count=int(
                            _float_field(row, ["call_count", "Call Count", "calls"], 0.0)
                        ),
                        cycles=_float_field(row, ["cycles", "Cycles", "cycle"], 0.0),
                        running_time_us=_float_field(
                            row,
                            [
                                "running_time(us)",
                                "running time(us)",
                                "running_time",
                                "time(us)",
                                "Time(us)",
                                "duration(us)",
                            ],
                            0.0,
                        ),
                        component=normalize_component(
                            _str_field(row, ["component", "Component", "pipeline"])
                        )
                        if _str_field(row, ["component", "Component", "pipeline"])
                        else _infer_component_from_code(code),
                    )
                )
    return sorted(hotspots, key=lambda item: item.running_time_us, reverse=True)


def _infer_component_from_code(code: str) -> Optional[str]:
    lowered = code.lower()
    if "copyin" in lowered or "mte2" in lowered:
        return "mte2"
    if "copyout" in lowered or "mte3" in lowered:
        return "mte3"
    if "compute" in lowered or "vector" in lowered:
        return "vector"
    if "scalar" in lowered or "init" in lowered or "process" in lowered:
        return "scalar"
    return None


def _windows_from_hotspots(hotspots: Iterable[CodeHotspot]) -> List[TimeWindow]:
    windows: List[TimeWindow] = []
    cursor = 0.0
    for hotspot in hotspots:
        duration = hotspot.running_time_us
        windows.append(
            TimeWindow(
                index=len(windows),
                start_us=cursor,
                end_us=cursor + duration,
                component=hotspot.component or "unknown",
                name=hotspot.code,
                cycles=hotspot.cycles,
                source="code_hotspot",
            )
        )
        cursor += duration
    return windows


def _parse_msprof_stdout_summary(
    requested_root: Path, run_root: Path
) -> Optional[Dict[str, Any]]:
    stdout_path = _find_msprof_stdout(requested_root, run_root)
    if not stdout_path:
        return None
    text = stdout_path.read_text(encoding="utf-8", errors="replace")
    summary: Dict[str, Any] = {"path": str(stdout_path)}

    runtime_match = re.search(r"Model RUN TIME:\s*([0-9]+(?:\.[0-9]+)?)\s*ms", text)
    if runtime_match:
        summary["model_run_time_ms"] = float(runtime_match.group(1))
        summary["model_run_time_us"] = float(runtime_match.group(1)) * 1000.0

    tick_match = re.search(r"\[INFO\]\s+Total tick:\s*([0-9]+(?:\.[0-9]+)?)", text)
    if tick_match:
        summary["total_tick"] = float(tick_match.group(1))

    core_match = re.search(r"\[TmSim\]:\s*Run in .* core num is:\s*([0-9]+)", text)
    if core_match:
        summary["core_count"] = int(core_match.group(1))

    summary["profiling_success"] = "Profiling running finished. All task success." in text
    summary["model_stopped_successfully"] = "Model stopped successfully." in text
    if len(summary) == 3 and not summary["profiling_success"] and not summary["model_stopped_successfully"]:
        return None
    return summary


def _find_msprof_stdout(requested_root: Path, run_root: Path) -> Optional[Path]:
    candidates = [
        requested_root / "msprof_stdout.log",
        run_root / "msprof_stdout.log",
        requested_root.parent / "msprof_stdout.log",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    matches = sorted(requested_root.rglob("msprof_stdout.log"))
    return matches[0] if matches else None


def _windows_from_stdout_summary(
    stdout_summary: Optional[Dict[str, Any]]
) -> List[TimeWindow]:
    if not stdout_summary:
        return []
    duration_us = float(stdout_summary.get("model_run_time_us") or 0.0)
    if duration_us <= 0.0:
        return []
    return [
        TimeWindow(
            index=0,
            start_us=0.0,
            end_us=duration_us,
            component="unknown",
            name="msprof simulator model run",
            cycles=float(stdout_summary.get("total_tick") or 0.0),
            source=str(stdout_summary.get("path", "msprof_stdout.log")),
            raw=stdout_summary,
        )
    ]


class MsprofCommandBuilder:
    def __init__(
        self,
        executable: str,
        soc_version: str = "Ascend910B1",
        output: str = "./prof",
        core_id: Optional[int] = 0,
        kernel_name: Optional[str] = None,
        config: Optional[str] = None,
        aic_metrics: Optional[str] = "PipeUtilization,ResourceConflictRatio",
        launch_count: Optional[int] = 1,
    ) -> None:
        self.executable = executable
        self.soc_version = soc_version
        self.output = output
        self.core_id = core_id
        self.kernel_name = kernel_name
        self.config = config
        self.aic_metrics = aic_metrics
        self.launch_count = launch_count

    def simulator_command(self) -> List[str]:
        command = [
            "msprof",
            "op",
            "simulator",
            f"--soc-version={self.soc_version}",
            f"--output={self.output}",
        ]
        if self.core_id is not None:
            command.append(f"--core-id={self.core_id}")
        if self.kernel_name:
            command.append(f"--kernel-name={self.kernel_name}")
        if self.config:
            command.append(f"--config={self.config}")
        if self.aic_metrics:
            command.append(f"--aic-metrics={self.aic_metrics}")
        if self.launch_count is not None:
            command.append(f"--launch-count={self.launch_count}")
        command.append(self.executable)
        return command

    def shell_string(self) -> str:
        return " ".join(self.simulator_command())

    def quoted_shell_string(self) -> str:
        return " ".join(shlex.quote(item) for item in self.simulator_command())


@dataclass(frozen=True)
class MsprofRunRequest:
    executable: str
    output: str
    soc_version: str = "Ascend910B1"
    core_id: Optional[int] = 0
    kernel_name: Optional[str] = None
    config: Optional[str] = None
    aic_metrics: Optional[str] = "PipeUtilization,ResourceConflictRatio"
    launch_count: Optional[int] = 1
    env_script: Optional[str] = None
    cwd: Optional[str] = None
    timeout_seconds: Optional[float] = None


@dataclass(frozen=True)
class MsprofRunResult:
    command: List[str]
    shell_command: str
    wrapped_command: List[str]
    output: str
    cwd: Optional[str]
    environment: Dict[str, Any]
    executed: bool
    returncode: Optional[int]
    timed_out: bool
    stdout_path: str
    stderr_path: str
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def run_msprof_simulator(request: MsprofRunRequest) -> MsprofRunResult:
    output = _resolve_output_path(request.output)
    output.mkdir(parents=True, exist_ok=True)
    stdout_path = output / "msprof_stdout.log"
    stderr_path = output / "msprof_stderr.log"
    environment = probe_msprof_environment(request.soc_version)
    command_request = replace(request, output=str(output))
    command = build_msprof_simulator_command(command_request)
    builder = MsprofCommandBuilder(
        executable=request.executable,
        soc_version=request.soc_version,
        output=str(output),
        core_id=request.core_id,
        kernel_name=request.kernel_name,
        config=request.config,
        aic_metrics=request.aic_metrics,
        launch_count=request.launch_count,
    )
    env_script = _resolve_env_script_path(request.env_script)
    wrapped_command = _wrap_msprof_command(command, env_script, request.soc_version)

    try:
        completed = subprocess.run(
            wrapped_command,
            cwd=request.cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=request.timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        _write_process_log(stdout_path, exc.stdout)
        _write_process_log(stderr_path, exc.stderr)
        return MsprofRunResult(
            command=command,
            shell_command=builder.shell_string(),
            wrapped_command=wrapped_command,
            output=str(output),
            cwd=request.cwd,
            environment=environment,
            executed=True,
            returncode=None,
            timed_out=True,
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
            error=f"msprof simulator timed out after {request.timeout_seconds} seconds",
        )

    _write_process_log(stdout_path, completed.stdout)
    _write_process_log(stderr_path, completed.stderr)
    return MsprofRunResult(
        command=command,
        shell_command=builder.shell_string(),
        wrapped_command=wrapped_command,
        output=str(output),
        cwd=request.cwd,
        environment=environment,
        executed=True,
        returncode=completed.returncode,
        timed_out=False,
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        error=None if completed.returncode == 0 else "msprof simulator exited with a non-zero status",
    )


def build_msprof_simulator_command(request: MsprofRunRequest) -> List[str]:
    builder = MsprofCommandBuilder(
        executable=request.executable,
        soc_version=request.soc_version,
        output=request.output,
        core_id=request.core_id,
        kernel_name=request.kernel_name,
        config=request.config,
        aic_metrics=request.aic_metrics,
        launch_count=request.launch_count,
    )
    return builder.simulator_command()


def _resolve_output_path(output: str) -> Path:
    path = Path(output).expanduser()
    if path.is_absolute():
        return path
    return path.resolve()


def _wrap_msprof_command(
    command: List[str], env_script: Optional[str], soc_version: str
) -> List[str]:
    quoted_command = " ".join(shlex.quote(item) for item in command)
    if not env_script:
        return command
    shell_command = (
        f"export ASCEND_SOC_VERSION={shlex.quote(soc_version)} && "
        f"source {shlex.quote(env_script)} && {quoted_command}"
    )
    return [
        "bash",
        "-lc",
        shell_command,
    ]


def _resolve_env_script_path(env_script: Optional[str]) -> Optional[str]:
    if not env_script:
        return None
    path = Path(env_script).expanduser()
    if path.is_absolute():
        return str(path)
    return str(path.resolve())


def _write_process_log(path: Path, payload: Any) -> None:
    if payload is None:
        text = ""
    elif isinstance(payload, bytes):
        text = payload.decode("utf-8", errors="replace")
    else:
        text = str(payload)
    path.write_text(text, encoding="utf-8")


def probe_msprof_environment(soc_version: str = "Ascend910B1") -> Dict[str, Any]:
    ascend_home = _detect_ascend_home()
    _configure_local_cann_env(ascend_home, soc_version)
    msprof_path = shutil.which("msprof")
    if not msprof_path and ascend_home:
        candidate = Path(ascend_home) / "bin" / "msprof"
        if candidate.exists():
            msprof_path = str(candidate)
    simulator_lib = None
    if ascend_home:
        candidate = Path(ascend_home) / "tools" / "simulator" / soc_version / "lib"
        simulator_lib = str(candidate)
    runtime_library_dirs = _runtime_library_dirs(ascend_home, soc_version)
    runtime_libraries = {
        name: _find_library(name, runtime_library_dirs)
        for name in ["libascend_hal.so", "libdcmi.so"]
    }
    missing_runtime_libraries = [
        name for name, path in runtime_libraries.items() if path is None
    ]

    issues = []
    if platform.system() != "Linux":
        issues.append("CANN/msprof simulator is expected to run in a Linux environment.")
    if not msprof_path:
        issues.append("`msprof` was not found on PATH.")
    if not ascend_home:
        issues.append("ASCEND_TOOLKIT_HOME or ASCEND_HOME_PATH is not set.")
    elif simulator_lib and not Path(simulator_lib).exists():
        issues.append(f"Simulator library path does not exist: {simulator_lib}")
    if missing_runtime_libraries:
        issues.append(
            "Ascend driver/runtime libraries are missing: "
            + ", ".join(missing_runtime_libraries)
        )

    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "msprof": msprof_path,
        "ascend_toolkit_home": ascend_home,
        "soc_version": soc_version,
        "simulator_lib": simulator_lib,
        "ld_library_path_contains_simulator": bool(
            simulator_lib and simulator_lib in os.environ.get("LD_LIBRARY_PATH", "")
        ),
        "driver_runtime_library_dirs": [str(path) for path in runtime_library_dirs],
        "runtime_libraries": runtime_libraries,
        "missing_runtime_libraries": missing_runtime_libraries,
        "ld_library_path_contains_driver_runtime": _ld_contains_any(runtime_library_dirs),
        "ready": not issues,
        "issues": issues,
        "requires_physical_hardware": False,
        "notes": [
            "`msprof op simulator` is a simulator profiling path; it still requires CANN/msprof and simulator libraries.",
            "The target workload must be built for simulator use; add -g when source hotspots are needed.",
            "Simulator profiling is single-card oriented; applications should use device/card 0.",
        ],
        "example_command": MsprofCommandBuilder(
            executable="./ascendc_kernels_bbit",
            soc_version=soc_version,
            output="./prof",
            core_id=0,
            aic_metrics="PipeUtilization,ResourceConflictRatio",
            launch_count=1,
        ).shell_string(),
    }


def _first_existing_env(names: List[str]) -> Optional[str]:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def _detect_ascend_home() -> Optional[str]:
    existing = _first_existing_env(["ASCEND_TOOLKIT_HOME", "ASCEND_HOME_PATH"])
    if existing:
        return existing

    home = Path.home()
    candidates = [
        home / "Ascend" / "ascend-toolkit" / "latest",
        Path("/usr/local/Ascend/ascend-toolkit/latest"),
    ]
    for candidate in candidates:
        if (candidate / "bin" / "msprof").exists():
            return str(candidate)
    return None


def _configure_local_cann_env(ascend_home: Optional[str], soc_version: str) -> None:
    if not ascend_home:
        return
    os.environ.setdefault("ASCEND_TOOLKIT_HOME", ascend_home)
    os.environ.setdefault("ASCEND_HOME_PATH", ascend_home)
    bin_path = str(Path(ascend_home) / "bin")
    current_path = os.environ.get("PATH", "")
    if bin_path not in current_path.split(os.pathsep):
        os.environ["PATH"] = bin_path + os.pathsep + current_path
    simulator_lib = str(Path(ascend_home) / "tools" / "simulator" / soc_version / "lib")
    ld_library_path = os.environ.get("LD_LIBRARY_PATH", "")
    if Path(simulator_lib).exists() and simulator_lib not in ld_library_path.split(os.pathsep):
        os.environ["LD_LIBRARY_PATH"] = simulator_lib + os.pathsep + ld_library_path
        ld_library_path = os.environ["LD_LIBRARY_PATH"]
    for directory in _runtime_library_dirs(ascend_home, soc_version):
        entry = str(directory)
        if directory.exists() and entry not in ld_library_path.split(os.pathsep):
            os.environ["LD_LIBRARY_PATH"] = entry + os.pathsep + ld_library_path
            ld_library_path = os.environ["LD_LIBRARY_PATH"]


def _runtime_library_dirs(ascend_home: Optional[str], soc_version: str) -> List[Path]:
    candidates: List[Path] = []
    for env_name in ["ASCEND_DRIVER_PATH", "ASCEND_RUNTIME_PATH"]:
        value = os.environ.get(env_name)
        if value:
            root = Path(value)
            candidates.extend(
                [
                    root,
                    root / "lib64",
                    root / "lib64" / "driver",
                    root / "driver" / "lib64",
                    root / "tools" / "dcmi",
                ]
            )
    if ascend_home:
        home = Path(ascend_home)
        candidates.extend(
            [
                home / "runtime" / "lib64",
            ]
        )
    candidates.extend(
        [
            Path.home() / "Ascend" / "driver" / "lib64",
            Path.home() / "Ascend" / "driver" / "lib64" / "driver",
            Path.home() / "Ascend" / "driver" / "tools" / "dcmi",
            Path("/usr/local/Ascend/driver/lib64"),
            Path("/usr/local/Ascend/driver/lib64/driver"),
            Path("/usr/local/Ascend/driver/tools/dcmi"),
            Path("/usr/local/Ascend/runtime/lib64"),
        ]
    )
    deduped: List[Path] = []
    seen = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _find_library(name: str, directories: List[Path]) -> Optional[str]:
    for directory in directories:
        candidate = directory / name
        if candidate.exists():
            return str(candidate)
        if directory.exists():
            matches = sorted(directory.glob(f"{name}*"))
            if matches:
                return str(matches[0])
    return None


def _ld_contains_any(directories: List[Path]) -> bool:
    entries = set(os.environ.get("LD_LIBRARY_PATH", "").split(os.pathsep))
    return any(str(directory) in entries for directory in directories if directory.exists())


def _summarize_artifacts(
    requested_root: Path,
    run_root: Path,
    trace_path: Optional[Path],
    stdout_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    code_csvs = [str(path) for path in sorted(run_root.rglob("*_code_exe.csv"))]
    instr_csvs = [str(path) for path in sorted(run_root.rglob("*_instr_exe.csv"))]
    visualize = [str(path) for path in sorted(run_root.rglob("visualize_data.bin"))]
    stdout_summary = stdout_summary or _parse_msprof_stdout_summary(requested_root, run_root)
    return {
        "requested_root": str(requested_root),
        "run_root": str(run_root),
        "trace_json": str(trace_path) if trace_path else None,
        "code_hotspot_csvs": code_csvs,
        "instruction_csvs": instr_csvs,
        "visualize_data": visualize,
        "msprof_stdout_summary": stdout_summary,
        "has_trace": trace_path is not None,
        "has_code_hotspots": bool(code_csvs),
        "has_instruction_csv": bool(instr_csvs),
        "has_visualize_data": bool(visualize),
        "has_msprof_stdout_summary": bool(stdout_summary),
    }


def _float_field(raw: Dict[str, Any], names: List[str], default: float) -> float:
    for name in names:
        value = raw.get(name)
        if value not in (None, ""):
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return default


def _str_field(raw: Dict[str, Any], names: List[str]) -> str:
    for name in names:
        value = raw.get(name)
        if value not in (None, ""):
            return str(value).strip()
    return ""
