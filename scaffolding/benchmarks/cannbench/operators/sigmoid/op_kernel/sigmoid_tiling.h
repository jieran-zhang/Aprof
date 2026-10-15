#pragma once
#include <algorithm>
#include <cstdint>

enum SigmoidDType : uint32_t {
    SIGMOID_FLOAT16 = 0,
    SIGMOID_FLOAT32 = 1,
    SIGMOID_BFLOAT16 = 2,
};

struct SigmoidTilingData {
    uint64_t totalLength;
    uint64_t blockLength;
    uint32_t blockNum;
    uint32_t tileElements;
    uint32_t dtype;
};

inline SigmoidTilingData ComputeSigmoidTiling(uint64_t n, uint32_t dtype, int64_t cores) {
    SigmoidTilingData t{};
    t.totalLength = n;
    const uint64_t useful = std::max<uint64_t>(1, (n + 4095) / 4096);
    t.blockNum = static_cast<uint32_t>(std::max<int64_t>(1, std::min<int64_t>(cores, useful)));
    t.blockLength = (n + t.blockNum - 1) / t.blockNum;
    // One input/output queue, two FP32 cast buffers, and Sigmoid's stack buffer fit in 192 KiB UB.
    t.tileElements = 4096;
    t.dtype = dtype;
    return t;
}
