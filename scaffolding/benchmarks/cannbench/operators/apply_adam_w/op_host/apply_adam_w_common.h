#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include "../op_kernel/apply_adam_w_tiling.h"

inline ApplyAdamWTilingData ComputeApplyAdamWTiling(
    uint64_t numel, uint32_t dtypeCode, uint64_t availableCores, uint64_t ubBytes,
    double lr, double beta1, double beta2, double weightDecay, double epsilon,
    int64_t step, bool maximize)
{
    if (numel == 0 || availableCores == 0 || ubBytes < 32768) throw std::invalid_argument("invalid device or tensor size");
    if (step < 1 || beta1 < 0.0 || beta1 >= 1.0 || beta2 < 0.0 || beta2 >= 1.0)
        throw std::invalid_argument("step must be >=1 and beta values in [0,1)");
    const uint64_t elemBytes = dtypeCode == APPLY_ADAM_W_FLOAT32 ? 4 : 2;
    const uint64_t candidate = std::max<uint64_t>(1, (numel * elemBytes + 4095) / 4096);
    const uint64_t cores = std::min(candidate, availableCores);
    const uint64_t average = (numel + cores - 1) / cores;
    const uint64_t blockFormer = ((average + 511) / 512) * 512;
    const uint64_t blockNum = (numel + blockFormer - 1) / blockFormer;
    const uint64_t blockTail = numel - (blockNum - 1) * blockFormer;

    // Select modes 1/2 require 8 KiB free UB on A2. In addition to the tensor
    // buffers, reserve a 256-byte-aligned bit mask and 2 KiB implementation margin.
    constexpr uint64_t SELECT_TEMP_BYTES = 8192;
    constexpr uint64_t FIXED_RESERVE_BYTES = 2048;
    constexpr uint64_t COPY_BLOCK_LEN_MAX = 2097151; // DataCopyExtParams::blockLen (bytes).
    constexpr uint64_t ALIGN_ELEMENTS = 64;          // FP32 Compare count: 256-byte aligned.
    if (ubBytes <= SELECT_TEMP_BYTES + FIXED_RESERVE_BYTES) throw std::runtime_error("UB is too small");
    // FP32 has five FP32 queues. Half/BF16 has four raw input queues, one raw
    // output queue, and five FP32 compute buffers.
    const uint64_t bytesPerElement = dtypeCode == APPLY_ADAM_W_FLOAT32 ? 20 : 30;
    const uint64_t copyElemBytes = dtypeCode == APPLY_ADAM_W_FLOAT32 ? 4 : 2;
    const uint64_t apiMaxElements = COPY_BLOCK_LEN_MAX / copyElemBytes;
    uint64_t ubFormer = std::min((ubBytes - SELECT_TEMP_BYTES - FIXED_RESERVE_BYTES) / bytesPerElement,
                                 std::min<uint64_t>(apiMaxElements, std::numeric_limits<int32_t>::max()));
    ubFormer = (ubFormer / ALIGN_ELEMENTS) * ALIGN_ELEMENTS;
    while (ubFormer > 0) {
        const uint64_t maskBytes = (((ubFormer + 7) / 8 + 255) / 256) * 256;
        if (ubFormer <= (std::numeric_limits<uint64_t>::max() - maskBytes - SELECT_TEMP_BYTES -
                         FIXED_RESERVE_BYTES) / bytesPerElement) {
            const uint64_t allocated = ubFormer * bytesPerElement + maskBytes +
                                       SELECT_TEMP_BYTES + FIXED_RESERVE_BYTES;
            if (allocated <= ubBytes) break;
        }
        ubFormer -= ALIGN_ELEMENTS;
    }
    if (ubFormer == 0) throw std::runtime_error("UB is too small");

    auto loops = [ubFormer](uint64_t n) { return static_cast<uint32_t>((n + ubFormer - 1) / ubFormer); };
    auto tail = [ubFormer](uint64_t n) {
        return static_cast<uint32_t>(n - ((n + ubFormer - 1) / ubFormer - 1) * ubFormer);
    };
    const double denom1d = 1.0 - std::pow(beta1, static_cast<double>(step));
    const double denom2d = 1.0 - std::pow(beta2, static_cast<double>(step));
    if (!std::isfinite(denom1d) || !std::isfinite(denom2d) || denom1d <= 0.0 || denom2d <= 0.0)
        throw std::invalid_argument("invalid bias correction denominator");
    const float denom1 = static_cast<float>(denom1d);
    const float denom2 = static_cast<float>(denom2d);

    ApplyAdamWTilingData t{};
    t.totalLength = numel; t.blockFormer = blockFormer; t.blockTail = blockTail;
    t.blockNum = static_cast<uint32_t>(blockNum); t.ubFormer = static_cast<uint32_t>(ubFormer);
    t.loopsFormer = loops(blockFormer); t.tailFormer = tail(blockFormer);
    t.loopsTail = loops(blockTail); t.tailTail = tail(blockTail); t.dtypeCode = dtypeCode;
    t.beta1 = static_cast<float>(beta1); t.beta2 = static_cast<float>(beta2);
    t.oneMinusBeta1 = static_cast<float>(1.0 - beta1); t.oneMinusBeta2 = static_cast<float>(1.0 - beta2);
    t.invBias1 = 1.0f / denom1; t.invBias2 = 1.0f / denom2;
    t.weightDecay = static_cast<float>(weightDecay); t.epsilon = static_cast<float>(epsilon);
    t.signedLr = static_cast<float>(maximize ? lr : -lr);
    t.quietNanBits = 0x7FC00000U;
    t.positiveInfBits = 0x7F800000U;
    t.negativeInfBits = 0xFF800000U;
    return t;
}
