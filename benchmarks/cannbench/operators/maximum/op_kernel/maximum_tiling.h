#pragma once
#include <algorithm>
#include <cstdint>
#include <stdexcept>
#include <vector>

enum MaximumDType : uint32_t {
    MAX_FLOAT16 = 0,
    MAX_FLOAT32 = 1,
    MAX_BFLOAT16 = 2,
    MAX_INT8 = 3,
    MAX_INT32 = 4,
    MAX_INT64 = 5,
};

struct MaximumTilingData {
    uint64_t totalLength;
    uint64_t blockLength;
    uint64_t outShape[8];
    uint64_t x1Stride[8];
    uint64_t x2Stride[8];
    uint32_t blockNum;
    uint32_t tileElements;
    uint32_t dtype;
    uint32_t rank;
    uint32_t sameShape;
};

inline MaximumTilingData ComputeMaximumTiling(
    const std::vector<uint64_t> &x1Shape, const std::vector<uint64_t> &x2Shape,
    uint32_t dtype, int64_t cores) {
    if (x1Shape.empty() || x2Shape.empty() || x1Shape.size() > 8 || x2Shape.size() > 8)
        throw std::invalid_argument("rank must be in [1, 8]");
    MaximumTilingData t{};
    t.rank = static_cast<uint32_t>(std::max(x1Shape.size(), x2Shape.size()));
    t.dtype = dtype;
    t.tileElements = 4096;
    t.sameShape = x1Shape == x2Shape;
    std::vector<uint64_t> a(t.rank, 1), b(t.rank, 1);
    std::copy(x1Shape.begin(), x1Shape.end(), a.begin() + t.rank - x1Shape.size());
    std::copy(x2Shape.begin(), x2Shape.end(), b.begin() + t.rank - x2Shape.size());
    uint64_t aStride = 1, bStride = 1, total = 1;
    for (int i = static_cast<int>(t.rank) - 1; i >= 0; --i) {
        if (a[i] != b[i] && a[i] != 1 && b[i] != 1)
            throw std::invalid_argument("incompatible broadcast shapes");
        t.outShape[i] = std::max(a[i], b[i]);
        t.x1Stride[i] = a[i] == 1 ? 0 : aStride;
        t.x2Stride[i] = b[i] == 1 ? 0 : bStride;
        aStride *= a[i]; bStride *= b[i]; total *= t.outShape[i];
    }
    t.totalLength = total;
    const uint64_t useful = std::max<uint64_t>(1, (total + 4095) / 4096);
    t.blockNum = static_cast<uint32_t>(std::max<int64_t>(1, std::min<int64_t>(cores, useful)));
    t.blockLength = (total + t.blockNum - 1) / t.blockNum;
    return t;
}
