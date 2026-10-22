#pragma once
#include <algorithm>
#include <cstdint>

enum MishDType : uint32_t {
    MISH_FLOAT16 = 0,
    MISH_FLOAT32 = 1,
    MISH_BFLOAT16 = 2,
};

struct MishTilingData {
    uint64_t totalLength;
    uint64_t blockLength;
    uint32_t blockNum;
    uint32_t tileElements;
    uint32_t dtype;
};

inline MishTilingData ComputeMishTiling(uint64_t n, uint32_t dtype, int64_t cores) {
    MishTilingData t{};
    t.totalLength = n;
    const uint64_t useful = std::max<uint64_t>(1, (n + 4095) / 4096);
    t.blockNum = static_cast<uint32_t>(std::max<int64_t>(1, std::min<int64_t>(cores, useful)));
    t.blockLength = (n + t.blockNum - 1) / t.blockNum;
    t.tileElements = 2048;
    t.dtype = dtype;
    return t;
}
