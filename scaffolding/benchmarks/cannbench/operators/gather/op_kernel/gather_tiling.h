#pragma once
#include <algorithm>
#include <cstdint>
#include <stdexcept>
#include <vector>

enum GatherIndexDType : uint32_t { GATHER_INDEX_INT8 = 0, GATHER_INDEX_INT32 = 1, GATHER_INDEX_INT64 = 2 };

struct GatherTilingData {
    uint64_t totalLength;
    uint64_t blockLength;
    uint64_t indexShape[8];
    uint64_t xStride[8];
    uint64_t gatherDimSize;
    uint32_t blockNum;
    uint32_t rank;
    uint32_t dim;
    uint32_t xItemBytes;
    uint32_t indexDtype;
};

inline GatherTilingData ComputeGatherTiling(const std::vector<uint64_t> &xShape,
                                             const std::vector<uint64_t> &indexShape,
                                             uint32_t dim, uint32_t xItemBytes,
                                             uint32_t indexDtype, int64_t cores) {
    if (xShape.empty() || xShape.size() > 8 || xShape.size() != indexShape.size())
        throw std::invalid_argument("x and index ranks must match and be in [1, 8]");
    if (dim >= xShape.size()) throw std::invalid_argument("dim must be in [0, rank)");
    GatherTilingData t{};
    t.rank = static_cast<uint32_t>(xShape.size());
    t.dim = dim;
    t.xItemBytes = xItemBytes;
    t.indexDtype = indexDtype;
    t.gatherDimSize = xShape[dim];
    uint64_t stride = 1, total = 1;
    for (int d = static_cast<int>(t.rank) - 1; d >= 0; --d) {
        if (static_cast<uint32_t>(d) != dim && indexShape[d] > xShape[d])
            throw std::invalid_argument("index shape exceeds x shape outside gather dim");
        if (xShape[d] == 0 || indexShape[d] == 0)
            throw std::invalid_argument("zero-sized dimensions are outside the supported range");
        t.indexShape[d] = indexShape[d];
        t.xStride[d] = stride;
        stride *= xShape[d];
        total *= indexShape[d];
    }
    t.totalLength = total;
    const uint64_t available = static_cast<uint64_t>(std::max<int64_t>(1, cores));
    const uint64_t useful = std::max<uint64_t>(1, (total + 4095) / 4096);
    t.blockNum = static_cast<uint32_t>(std::min<uint64_t>(useful, available));
    t.blockLength = (total + t.blockNum - 1) / t.blockNum;
    return t;
}
