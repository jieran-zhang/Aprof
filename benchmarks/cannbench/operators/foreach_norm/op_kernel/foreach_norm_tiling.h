#pragma once
#include <algorithm>
#include <cstdint>

enum ForeachNormDType : uint32_t {
    FOREACH_NORM_FLOAT16 = 0,
    FOREACH_NORM_FLOAT32 = 1,
    FOREACH_NORM_BFLOAT16 = 2,
};

enum ForeachNormMode : uint32_t {
    FOREACH_NORM_GENERAL = 0,
    FOREACH_NORM_INF = 1,
    FOREACH_NORM_ZERO = 2,
};

struct ForeachNormTilingData {
    uint64_t totalLength;
    uint64_t blockLength;
    uint32_t blockNum;
    uint32_t tileElements;
    uint32_t dtype;
    uint32_t mode;
    float scalar;
};

inline ForeachNormTilingData ComputeForeachNormTiling(
    uint64_t n, uint32_t dtype, int64_t cores, float scalar) {
    ForeachNormTilingData t{};
    t.totalLength = n;
    t.blockNum = static_cast<uint32_t>(std::max<int64_t>(
        1, std::min<int64_t>(cores, static_cast<int64_t>((n + 262143) / 262144))));
    t.blockLength = (n + t.blockNum - 1) / t.blockNum;
    t.tileElements = 1024;
    t.dtype = dtype;
    t.scalar = scalar;
    t.mode = scalar == 0.0f ? FOREACH_NORM_ZERO
        : (scalar == __builtin_inff() ? FOREACH_NORM_INF : FOREACH_NORM_GENERAL);
    return t;
}
