#pragma once
#include <algorithm>
#include <cstdint>
#include <stdexcept>
#include <vector>

struct StridedSliceTilingData {
    uint64_t totalLength;
    uint64_t blockLength;
    uint64_t sourceBase;
    uint64_t outputShape[8];
    uint64_t sourceStep[8];
    uint32_t blockNum;
    uint32_t outputRank;
    uint32_t itemBytes;
};

inline int64_t NormalizeBound(int64_t value, uint64_t dim) {
    if (value < 0) value += static_cast<int64_t>(dim);
    return value;
}

inline StridedSliceTilingData ComputeStridedSliceTiling(
    const std::vector<uint64_t> &shape, const std::vector<int64_t> &begin,
    const std::vector<int64_t> &end, const std::vector<int64_t> &strides,
    uint64_t beginMask, uint64_t endMask, uint64_t ellipsisMask,
    uint64_t shrinkMask, uint64_t newAxisMask, uint32_t itemBytes, int64_t cores) {
    if (shape.empty() || shape.size() > 8) throw std::invalid_argument("input rank must be in [1, 8]");
    if (begin.size() != end.size() || begin.size() != strides.size() || begin.size() > 8)
        throw std::invalid_argument("begin/end/strides lengths must match and be <= 8");
    if (ellipsisMask && (ellipsisMask & (ellipsisMask - 1)))
        throw std::invalid_argument("ellipsis_mask may contain at most one bit");
    std::vector<uint64_t> xStride(shape.size());
    uint64_t stride = 1;
    for (int d = static_cast<int>(shape.size()) - 1; d >= 0; --d) {
        xStride[d] = stride; stride *= shape[d];
    }
    uint32_t newCount = 0;
    for (uint32_t p = 0; p < begin.size(); ++p) if ((newAxisMask >> p) & 1U) ++newCount;
    const int ellipsisPos = ellipsisMask ? __builtin_ctzll(ellipsisMask) : -1;
    const int ellipsisDims = ellipsisPos >= 0
        ? std::max<int>(0, static_cast<int>(shape.size()) - (static_cast<int>(begin.size()) - newCount - 1)) : 0;

    StridedSliceTilingData t{}; t.itemBytes = itemBytes;
    uint32_t inputDim = 0, param = 0, outDim = 0;
    auto append = [&](uint64_t size, uint64_t step) {
        if (outDim >= 8) throw std::invalid_argument("output rank exceeds 8");
        t.outputShape[outDim] = size; t.sourceStep[outDim] = step; ++outDim;
    };
    while (inputDim < shape.size() || param < begin.size()) {
        if (param < begin.size() && ((newAxisMask >> param) & 1U)) {
            append(1, 0); ++param; continue;
        }
        if (ellipsisPos >= 0 && static_cast<int>(param) == ellipsisPos) {
            for (int i = 0; i < ellipsisDims; ++i) {
                append(shape[inputDim], xStride[inputDim]); ++inputDim;
            }
            ++param; continue;
        }
        if (inputDim < shape.size() && param < begin.size()) {
            const int64_t dim = static_cast<int64_t>(shape[inputDim]);
            const int64_t s = strides[param];
            if (s == 0) throw std::invalid_argument("stride must not be zero");
            int64_t b = NormalizeBound(begin[param], shape[inputDim]);
            int64_t e = NormalizeBound(end[param], shape[inputDim]);
            if ((beginMask >> param) & 1U) b = s > 0 ? 0 : dim - 1;
            if ((endMask >> param) & 1U) e = s > 0 ? dim : -1;
            if ((shrinkMask >> param) & 1U) {
                if (b < 0 || b >= dim) throw std::invalid_argument("shrink index out of range");
                t.sourceBase += static_cast<uint64_t>(b) * xStride[inputDim];
            } else {
                // The benchmark golden performs only negative-index adjustment before Python slicing.
                // Its 20 cases use positive strides, but retain a complete length formula here.
                int64_t length = 0;
                if (s > 0) {
                    b = std::max<int64_t>(0, std::min<int64_t>(b, dim));
                    e = std::max<int64_t>(0, std::min<int64_t>(e, dim));
                    if (e > b) length = (e - b + s - 1) / s;
                } else {
                    b = std::max<int64_t>(-1, std::min<int64_t>(b, dim - 1));
                    e = std::max<int64_t>(-1, std::min<int64_t>(e, dim - 1));
                    const int64_t step = -s;
                    if (b > e) length = (b - e + step - 1) / step;
                }
                if (length == 0) throw std::invalid_argument("zero-sized outputs are not supported by this runner");
                t.sourceBase += static_cast<uint64_t>(b) * xStride[inputDim];
                append(static_cast<uint64_t>(length), static_cast<uint64_t>(s * static_cast<int64_t>(xStride[inputDim])));
            }
            ++inputDim; ++param;
        } else if (inputDim < shape.size()) {
            append(shape[inputDim], xStride[inputDim]); ++inputDim;
        } else {
            ++param;
        }
    }
    t.outputRank = outDim; t.totalLength = 1;
    for (uint32_t d = 0; d < outDim; ++d) t.totalLength *= t.outputShape[d];
    const uint64_t available = static_cast<uint64_t>(std::max<int64_t>(1, cores));
    const uint64_t useful = std::max<uint64_t>(1, (t.totalLength + 4095) / 4096);
    t.blockNum = static_cast<uint32_t>(std::min<uint64_t>(available, useful));
    const uint64_t writeBlockElems = 64 / itemBytes;
    const uint64_t rawBlockLength = (t.totalLength + t.blockNum - 1) / t.blockNum;
    // Separate adjacent cores on 64-byte GM cache lines. Unaligned scalar-store
    // boundaries can make two vector cores update the same cache line and lose writes.
    t.blockLength = ((rawBlockLength + writeBlockElems - 1) / writeBlockElems) * writeBlockElems;
    return t;
}
