#pragma once
#include <algorithm>
#include <cstdint>

enum MaskedScaleDType : uint32_t {
    MS_FLOAT16 = 0,
    MS_FLOAT32 = 1,
    MS_BFLOAT16 = 2,
    MS_INT8 = 3,
    MS_UINT8 = 4,
};

struct MaskedScaleTilingData {
    uint64_t totalLength;
    uint64_t blockLength;
    uint32_t blockNum;
    uint32_t tileElements;
    uint32_t xDtype;
    uint32_t maskDtype;
    float scale;
};

inline MaskedScaleTilingData ComputeMaskedScaleTiling(
    uint64_t n, uint32_t xDtype, uint32_t maskDtype, int64_t cores, float scale) {
    MaskedScaleTilingData t{};
    t.totalLength = n;
    const uint64_t useful = std::max<uint64_t>(1, (n + 4095) / 4096);
    t.blockNum = static_cast<uint32_t>(std::max<int64_t>(1, std::min<int64_t>(cores, useful)));
    t.blockLength = (n + t.blockNum - 1) / t.blockNum;
    t.tileElements = 4096;
    t.xDtype = xDtype;
    t.maskDtype = maskDtype;
    t.scale = scale;
    return t;
}
