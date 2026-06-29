from __future__ import annotations

from aprof.core.models import CaseEvidence


def diagnose_label(evidence: CaseEvidence) -> tuple[str, str, str]:
    """Map normalized evidence to one AProf problem label.

    The current evaluator is intentionally simple and deterministic: injected kernels
    encode one primary cause in tiling/source metadata, and msprof evidence confirms
    whether profiling ran and what artifacts are available.
    """
    meta = evidence.metadata
    source = evidence.source
    artifacts = evidence.artifacts
    tile = int(meta.get("tile_length", 0) or 0)
    out = int(meta.get("output_elements", 0) or 0)
    tile_num = int(meta.get("tile_num", 0) or 0)
    tail = int(meta.get("tail_length", 0) or 0)
    blockdim = int(meta.get("blockdim", 1) or 1)
    variant = str(meta.get("variant", ""))

    if variant == "inject_blockdim":
        return "blockdim_too_small", "medium", "增加 blockDim 或按数据量重新切分，避免单 core 压力过高。"
    if source.get("inject_tail") or tail:
        return "tail_inefficient", "high", "优化 tail 分支，避免尾块额外 GM 往返或独立低效路径。"
    if tile and tile <= 32 and tile_num >= 4:
        return "tileLength_too_small", "high", "增大 tileLength，降低循环、同步和调度开销占比。"
    if source.get("inject_dynshape") or (tile > max(out, 1) and out <= 1024):
        return "fixed_tiling_dynamic_shape", "medium", "为动态 shape 分桶或按实际 shape 重新计算 tileLength。"
    if tile_num > max(1, (out + max(tile, 1) - 1) // max(tile, 1)) * 2:
        return "tileNum_unreasonable", "medium", "让 tileNum 回到 ceil(elemsPerCore/tileLength)，避免空转调度。"
    if tile >= 2048:
        return "tileLength_too_large", "medium", "减小 tileLength，降低 UB 压力并改善流水粒度。"
    if blockdim == 1 and out >= 256:
        return "blockdim_too_small", "medium", "增加 blockDim 或按数据量重新切分，避免单 core 压力过高。"
    if artifacts.get("has_trace"):
        return "baseline", "medium", "未观察到注入问题特征，保留 baseline。"
    return "insufficient_evidence", "low", "缺少 trace 或 CSV，需重新采集 msprof simulator 产物。"
