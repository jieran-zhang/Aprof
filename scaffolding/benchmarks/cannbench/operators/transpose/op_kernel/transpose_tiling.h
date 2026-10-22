#pragma once
#include <algorithm>
#include <cstdint>
#include <stdexcept>
#include <vector>

struct TransposeTilingData {
    uint64_t totalLength;
    uint64_t blockLength;
    uint64_t inputStride[8];
    uint64_t outputShape[8];
    uint32_t perm[8];
    uint32_t rank;
    uint32_t itemBytes;
    uint32_t blockNum;
};

inline TransposeTilingData ComputeTransposeTiling(const std::vector<uint64_t> &shape,
                                                   const std::vector<uint32_t> &perm,
                                                   uint32_t itemBytes, int64_t cores) {
    if (shape.empty() || shape.size() > 8 || shape.size() != perm.size())
        throw std::invalid_argument("rank must be in [1,8] and perm must match rank");
    TransposeTilingData t{}; t.rank = shape.size(); t.itemBytes = itemBytes; t.totalLength = 1;
    bool seen[8]{};
    for (uint32_t d = 0; d < t.rank; ++d) {
        if (perm[d] >= t.rank || seen[perm[d]]) throw std::invalid_argument("perm is not a permutation");
        seen[perm[d]] = true; t.perm[d] = perm[d]; t.outputShape[d] = shape[perm[d]]; t.totalLength *= shape[d];
    }
    uint64_t stride = 1;
    for (int d = static_cast<int>(t.rank) - 1; d >= 0; --d) { t.inputStride[d] = stride; stride *= shape[d]; }
    const uint64_t target = 4096;
    t.blockNum = std::max<uint32_t>(1, std::min<uint64_t>(std::max<int64_t>(1, cores), (t.totalLength + target - 1) / target));
    t.blockLength = (t.totalLength + t.blockNum - 1) / t.blockNum;
    return t;
}
