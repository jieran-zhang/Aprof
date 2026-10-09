#pragma once
#include <algorithm>
#include <cstdint>

enum ForeachAddcdivDType : uint32_t {
    FOREACH_ADCDIV_FLOAT16 = 0,
    FOREACH_ADCDIV_FLOAT32 = 1,
    FOREACH_ADCDIV_BFLOAT16 = 2,
};

struct ForeachAddcdivTilingData {
    uint64_t totalLength;
    uint64_t blockLength;
    uint32_t blockNum;
    uint32_t tileElements;
    uint32_t dtype;
    float scalar;
};

inline ForeachAddcdivTilingData ComputeForeachAddcdivTiling(
    uint64_t n, uint32_t dtype, int64_t cores, float scalar) {
    ForeachAddcdivTilingData t{};
    t.totalLength = n;
    const uint64_t useful = std::max<uint64_t>(1, (n + 2047) / 2048);
    t.blockNum = static_cast<uint32_t>(
        std::max<int64_t>(1, std::min<int64_t>(cores, useful)));
    t.blockLength = (n + t.blockNum - 1) / t.blockNum;
    t.tileElements = 2048;
    t.dtype = dtype;
    t.scalar = scalar;
    return t;
}
