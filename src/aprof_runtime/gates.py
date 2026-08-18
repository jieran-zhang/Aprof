from __future__ import annotations

import math
import random
import statistics
import hashlib
from dataclasses import replace

from .contracts import (
    CandidateDraft,
    EMPTY_ARTIFACT_SHA256,
    GateConfig,
    GateEvidence,
    GateOutcome,
    GateRequest,
    GateStageStatus,
    GateVerdict,
    SCHEMA_VERSION,
)
from .jsonio import content_hash, to_primitive


def _median(samples: tuple[float, ...]) -> float:
    return float(statistics.median(samples)) if samples else 0.0


def _cv(samples: tuple[float, ...]) -> float:
    if len(samples) < 2:
        return 0.0
    mean = statistics.fmean(samples)
    return float(statistics.stdev(samples) / mean)


def _paired_estimate(
    baseline: tuple[float, ...], candidate: tuple[float, ...], config: GateConfig, candidate_id: str
) -> tuple[float, float]:
    log_ratios = [math.log(before / after) for before, after in zip(baseline, candidate, strict=True)]
    estimate = statistics.fmean(log_ratios)
    seed = int.from_bytes(hashlib.sha256(candidate_id.encode("utf-8")).digest()[:8], "big")
    generator = random.Random(seed)
    count = len(log_ratios)
    bootstrap = sorted(
        statistics.fmean(log_ratios[generator.randrange(count)] for _ in range(count))
        for _ in range(config.bootstrap_resamples)
    )
    alpha = 1.0 - config.lcb_confidence
    lower_index = max(0, min(len(bootstrap) - 1, int(alpha * len(bootstrap))))
    return math.exp(estimate), math.exp(bootstrap[lower_index])


class CandidateGate:
    """Deterministic state machine that exclusively owns candidate verdicts.

    Agent-authored data stops at CandidateDraft and GateEvidence.  In particular,
    neither contract has ``selected_as_best``; selection happens here over the
    complete candidate batch after all hard gates have passed.
    """

    def evaluate(self, request: GateRequest) -> tuple[GateOutcome, ...]:
        # Dataclasses are public Python APIs as well as parser outputs. Re-parse
        # the config here so a directly constructed GateRequest cannot bypass
        # the runtime-owned production floors.
        GateConfig.from_dict(to_primitive(request.config), "$.config")
        evidence = {item.candidate_id: item for item in request.evidence}
        preliminary = [self._evaluate_one(item, evidence[item.candidate_id], request.config) for item in request.candidates]

        eligible = [item for item in preliminary if item.eligible]
        winner_id: str | None = None
        if eligible:
            winner_id = min(eligible, key=lambda item: (-item.utility, item.candidate_id)).candidate_id

        outcomes: list[GateOutcome] = []
        request_payload = to_primitive(request)
        for item in preliminary:
            selected = item.candidate_id == winner_id
            without_hash = {
                **to_primitive(replace(item, selected_as_best=selected)),
                "decision_hash": "",
                "gate_request": request_payload,
            }
            decision_hash = content_hash(without_hash)
            outcomes.append(replace(item, selected_as_best=selected, decision_hash=decision_hash))
        return tuple(outcomes)

    def _evaluate_one(self, draft: CandidateDraft, evidence: GateEvidence, config: GateConfig) -> GateOutcome:
        candidate_id = draft.candidate_id
        if draft.transformation_id == "transformation.noop":
            return self._evaluate_noop(draft, evidence)
        baseline = _median(evidence.baseline_samples_ns)
        candidate = _median(evidence.candidate_samples_ns)
        speedup = 0.0
        speedup_lcb = 0.0
        cv = max(_cv(evidence.baseline_samples_ns), _cv(evidence.candidate_samples_ns))
        max_regression = max(evidence.heldout_regressions, default=0.0)
        utility = -1.0
        path = ["draft", "static_review"]
        reasons: list[str] = []

        verdict = GateVerdict.STATIC_REJECTED
        eligible = False
        if evidence.static_review is not GateStageStatus.PASSED:
            verdict = GateVerdict.STATIC_REJECTED
            reasons.append(f"static review status is {evidence.static_review.value}")
        elif evidence.build is not GateStageStatus.PASSED:
            path.append("build")
            verdict = GateVerdict.BUILD_FAILED
            reasons.append(f"build status is {evidence.build.value}")
        else:
            path.extend(("build", "accuracy"))
            if evidence.accuracy is not GateStageStatus.PASSED or evidence.semantic is not GateStageStatus.PASSED:
                verdict = GateVerdict.ACCURACY_FAILED
                reasons.append(f"accuracy status is {evidence.accuracy.value}; semantic status is {evidence.semantic.value}")
            elif evidence.runtime is not GateStageStatus.PASSED:
                path.append("runtime")
                verdict = GateVerdict.RUNTIME_FAILED
                reasons.append(f"runtime status is {evidence.runtime.value}")
            else:
                path.extend(("runtime", "artifacts"))
                missing = sorted(set(config.required_artifacts) - evidence.artifacts.keys())
                if missing:
                    verdict = GateVerdict.ARTIFACTS_INCOMPLETE
                    reasons.append("missing required artifacts: " + ", ".join(missing))
                else:
                    path.append("measurement_stability")
                    paired = len(evidence.baseline_samples_ns) == len(evidence.candidate_samples_ns)
                    enough = len(evidence.baseline_samples_ns) >= config.min_pairs
                    if not paired or not enough:
                        verdict = GateVerdict.MEASUREMENT_UNSTABLE
                        reasons.append(
                            f"paired measurements require equal arrays with at least {config.min_pairs} pairs"
                        )
                    elif cv > config.max_cv:
                        verdict = GateVerdict.MEASUREMENT_UNSTABLE
                        reasons.append(f"candidate runtime cv {cv:.6g} exceeds {config.max_cv:.6g}")
                    else:
                        speedup, speedup_lcb = _paired_estimate(
                            evidence.baseline_samples_ns, evidence.candidate_samples_ns, config, candidate_id
                        )
                        utility = math.log(speedup) - max(0.0, max_regression)
                        path.append("mechanism_alignment")
                        if config.require_mechanism_alignment and evidence.mechanism_alignment is not True:
                            verdict = GateVerdict.ATTRIBUTION_UNCERTAIN
                            reasons.append("required mechanism alignment was not demonstrated")
                        else:
                            if evidence.mechanism_alignment is not True:
                                reasons.append("mechanism attribution is uncertain (non-blocking)")
                            path.append("heldout_regression")
                            if max_regression > config.max_heldout_regression:
                                verdict = GateVerdict.HELDOUT_REGRESSION
                                reasons.append(
                                    f"held-out regression {max_regression:.6g} exceeds {config.max_heldout_regression:.6g}"
                                )
                            else:
                                path.append("performance_gain")
                                if speedup_lcb < config.min_speedup_lcb:
                                    verdict = GateVerdict.STABLE_NO_GAIN
                                    reasons.append(
                                        f"paired speedup LCB {speedup_lcb:.6g} is below {config.min_speedup_lcb:.6g}"
                                    )
                                elif evidence.scope is not GateStageStatus.PASSED or evidence.portability is not GateStageStatus.PASSED:
                                    verdict = GateVerdict.BENCHMARK_SPECIALIZED_GAIN
                                    reasons.append(
                                        f"gain is benchmark-specialized; scope={evidence.scope.value}, portability={evidence.portability.value}"
                                    )
                                else:
                                    path.extend(("production_safety", "eligible"))
                                    verdict = GateVerdict.PRODUCTION_SAFE_GAIN
                                    eligible = True
                                    reasons.append("all machine gates passed")

        return GateOutcome(
            schema_version=SCHEMA_VERSION,
            candidate_id=candidate_id,
            verdict=verdict,
            state_path=tuple(path),
            baseline_median_ns=baseline,
            candidate_median_ns=candidate,
            speedup=speedup,
            speedup_lcb=speedup_lcb,
            pair_count=min(len(evidence.baseline_samples_ns), len(evidence.candidate_samples_ns)),
            measurement_protocol="paired_log_speedup_deterministic_bootstrap_lcb_v1",
            measurement_cv=cv,
            utility=utility,
            eligible=eligible,
            policy_update_eligible=True,
            selected_as_best=False,
            reasons=tuple(reasons),
            decision_hash="sha256:" + "0" * 64,
        )

    def _evaluate_noop(self, draft: CandidateDraft, evidence: GateEvidence) -> GateOutcome:
        reasons: list[str] = []
        if draft.source_hashes.baseline != draft.source_hashes.candidate:
            reasons.append("baseline and candidate source hashes differ")
        if draft.patch_artifact_hash != EMPTY_ARTIFACT_SHA256:
            reasons.append("NOOP patch artifact is not the canonical zero-byte artifact")
        if draft.parameters.get("no_mutation") is not True:
            reasons.append("parameters.no_mutation must be true")
        reason = draft.parameters.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            reasons.append("parameters.reason must be a non-empty string")
        if evidence.static_review is not GateStageStatus.PASSED:
            reasons.append(f"static review status is {evidence.static_review.value}; verified NOOP requires passed")
        if evidence.baseline_samples_ns or evidence.candidate_samples_ns:
            reasons.append("verified NOOP must not contain timing samples")
        if evidence.runtime is GateStageStatus.PASSED:
            reasons.append("verified NOOP must not claim a runtime execution")

        verified = not reasons
        return GateOutcome(
            schema_version=SCHEMA_VERSION,
            candidate_id=draft.candidate_id,
            verdict=GateVerdict.VERIFIED_NOOP if verified else GateVerdict.STATIC_REJECTED,
            state_path=("draft", "no_mutation", "verified_noop" if verified else "no_mutation_rejected"),
            baseline_median_ns=0.0,
            candidate_median_ns=0.0,
            speedup=1.0 if verified else 0.0,
            speedup_lcb=1.0 if verified else 0.0,
            pair_count=0,
            measurement_protocol="no_mutation_source_identity_v1",
            measurement_cv=0.0,
            utility=0.0 if verified else -1.0,
            eligible=False,
            policy_update_eligible=False,
            selected_as_best=False,
            reasons=(f"verified no mutation: {reason.strip()}",) if verified else tuple(reasons),
            decision_hash="sha256:" + "0" * 64,
        )
