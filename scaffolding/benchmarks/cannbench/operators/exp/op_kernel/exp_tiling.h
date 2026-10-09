#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>

enum ExpDType : uint32_t { EXP_FLOAT16 = 0, EXP_FLOAT32 = 1, EXP_BFLOAT16 = 2 };

struct ExpTilingData {
    uint64_t totalLength;
    uint64_t blockLength;
    uint32_t blockNum;
    uint32_t tileElements;
    uint32_t dtype;
    float multiplier;
    float shift;
};

inline ExpTilingData ComputeExpTiling(uint64_t n, uint32_t dtype, int64_t cores,
                                      float base, float scale, float shift) {
    ExpTilingData t{};
    t.totalLength = n;
    const uint64_t useful = std::max<uint64_t>(1, (n + 4095) / 4096);
    t.blockNum = static_cast<uint32_t>(std::max<int64_t>(1, std::min<int64_t>(cores, useful)));
    t.blockLength = (n + t.blockNum - 1) / t.blockNum;
    t.tileElements = 4096;
    t.dtype = dtype;
    t.multiplier = scale * (base > 0.0f ? std::log(base) : 1.0f);
    t.shift = shift * (base > 0.0f ? std::log(base) : 1.0f);
    return t;
}
