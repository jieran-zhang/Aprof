from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from aprof.metrics.architecture import load_architecture
from aprof.agents.diagnosis.attribution import analyze_observation
from aprof.reports.comparison import write_compare_report
from aprof.agents.profiling.harness import HarnessRequest, run_harness
from aprof.profiling.msprof import MsprofCommandBuilder, parse_msprof_simulator, probe_msprof_environment
from aprof.reports.analysis import write_analysis_report, write_environment_report
from aprof.integrations.cannbot import get_skill_markdown, list_skills, resolve_skill
from aprof.profiling.skills import skill_specs_to_dicts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aprof")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="Analyze msprof simulator output")
    analyze.add_argument("--input", required=True, help="msprof simulator output directory")
    analyze.add_argument("--arch", required=True, help="architecture config path")
    analyze.add_argument("--out", required=True, help="output report directory")

    diagnose = subparsers.add_parser(
        "diagnose", help="Run the AProf harness and emit potential problems"
    )
    diagnose.add_argument("--executable", help="program to run under msprof op simulator")
    diagnose.add_argument("--source-root", help="optional Ascend source directory")
    diagnose.add_argument("--input", help="existing msprof simulator output directory")
    diagnose.add_argument(
        "--profile-output",
        help="raw msprof output directory; defaults to OUT/raw when --run is used",
    )
    diagnose.add_argument("--arch", required=True, help="architecture config path")
    diagnose.add_argument("--out", required=True, help="output report directory")
    diagnose.add_argument("--soc-version", default="Ascend910B1")
    diagnose.add_argument("--operator-name", default="AscendC_Sample")
    diagnose.add_argument("--kernel-version", default="sample_v0")
    diagnose.add_argument("--shape", default="unknown")
    diagnose.add_argument("--data-type", default="unknown")
    diagnose.add_argument("--kernel-name")
    diagnose.add_argument("--config")
    diagnose.add_argument("--core-id", type=int, default=0)
    diagnose.add_argument(
        "--aic-metrics",
        default="PipeUtilization,ResourceConflictRatio",
        help="comma-separated msprof simulator AIC metrics; pass an empty string to disable",
    )
    diagnose.add_argument(
        "--launch-count",
        type=int,
        default=1,
        help="number of kernel launches msprof should collect",
    )
    diagnose.add_argument("--env-script", default="scripts/env_cann.sh")
    diagnose.add_argument("--cwd")
    diagnose.add_argument("--timeout-seconds", type=float)
    diagnose.add_argument("--run", action="store_true", help="execute msprof simulator")

    compare = subparsers.add_parser("compare", help="Compare two profiled variants")
    compare.add_argument("--before", required=True, help="before fixture/output directory")
    compare.add_argument("--after", required=True, help="after fixture/output directory")
    compare.add_argument("--arch", required=True, help="architecture config path")
    compare.add_argument("--out", required=True, help="output report directory")

    probe = subparsers.add_parser("probe-env", help="Check real msprof simulator readiness")
    probe.add_argument("--soc-version", default="Ascend910B1")
    probe.add_argument("--out", help="optional directory for environment report")

    command = subparsers.add_parser("command", help="Print a real msprof simulator command")
    command.add_argument("executable", help="program to run under msprof op simulator")
    command.add_argument("--soc-version", default="Ascend910B1")
    command.add_argument("--output", default="./prof")
    command.add_argument("--core-id", type=int, default=0)
    command.add_argument("--kernel-name")
    command.add_argument("--config")
    command.add_argument("--aic-metrics", default="PipeUtilization,ResourceConflictRatio")
    command.add_argument("--launch-count", type=int, default=1)

    subparsers.add_parser("skills", help="List available profiling skills")

    cannbot = subparsers.add_parser(
        "cannbot-skills", help="List or inspect CANNBot skills from third_party/cannbot-skills"
    )
    cannbot.add_argument("name", nargs="?", help="skill name, e.g. ops-profiling")
    cannbot.add_argument(
        "--show",
        action="store_true",
        help="print SKILL.md content when name is provided",
    )

    args = parser.parse_args(argv)

    if args.command == "analyze":
        architecture = load_architecture(args.arch)
        observation = parse_msprof_simulator(args.input)
        result = analyze_observation(observation, architecture)
        write_analysis_report(result, args.out)
        print(json.dumps(asdict(result.diagnosis), indent=2, ensure_ascii=False))
        return 0

    if args.command == "diagnose":
        if args.run and not args.executable:
            parser.error("diagnose --run requires --executable")
        if not args.run and not (args.input or args.profile_output):
            parser.error("diagnose without --run requires --input or --profile-output")
        result = run_harness(
            HarnessRequest(
                executable=args.executable,
                source_root=args.source_root,
                input_path=args.input,
                profile_output=args.profile_output,
                arch=args.arch,
                out_dir=args.out,
                run=args.run,
                soc_version=args.soc_version,
                operator_name=args.operator_name,
                kernel_version=args.kernel_version,
                shape=args.shape,
                data_type=args.data_type,
                kernel_name=args.kernel_name,
                config=args.config,
                core_id=args.core_id,
                aic_metrics=args.aic_metrics or None,
                launch_count=args.launch_count,
                env_script=args.env_script,
                cwd=args.cwd,
                timeout_seconds=args.timeout_seconds,
            )
        )
        print(json.dumps(result.problems.to_dict(), indent=2, ensure_ascii=False))
        return 0

    if args.command == "compare":
        write_compare_report(args.before, args.after, args.arch, args.out)
        print(f"comparison report written to {args.out}")
        return 0

    if args.command == "probe-env":
        payload = probe_msprof_environment(args.soc_version)
        if args.out:
            write_environment_report(payload, args.out)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    if args.command == "command":
        builder = MsprofCommandBuilder(
            executable=args.executable,
            soc_version=args.soc_version,
            output=args.output,
            core_id=args.core_id,
            kernel_name=args.kernel_name,
            config=args.config,
            aic_metrics=args.aic_metrics or None,
            launch_count=args.launch_count,
        )
        print(builder.shell_string())
        return 0

    if args.command == "skills":
        print(json.dumps(skill_specs_to_dicts(), indent=2, ensure_ascii=False))
        return 0

    if args.command == "cannbot-skills":
        if args.name:
            skill = resolve_skill(args.name)
            if args.show:
                print(get_skill_markdown(args.name))
            else:
                print(
                    json.dumps(
                        {
                            "name": skill.name,
                            "category": skill.category,
                            "path": str(skill.path),
                            "skill_md": str(skill.skill_md),
                        },
                        indent=2,
                        ensure_ascii=False,
                    )
                )
            return 0
        payload = [
            {
                "name": skill.name,
                "category": skill.category,
                "path": str(skill.path),
                "skill_md": str(skill.skill_md),
            }
            for skill in list_skills()
        ]
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    parser.error(f"unsupported command: {args.command}")
    return 2
