#pragma once
#include <algorithm>
#include <cstdint>
#include <stdexcept>
#include <vector>

enum ArgMaxDType : uint32_t {
    ARG_MAX_FLOAT16 = 0,
    ARG_MAX_FLOAT32 = 1,
    ARG_MAX_BFLOAT16 = 2,
    ARG_MAX_INT32 = 3,
    ARG_MAX_INT64 = 4,
};

struct ArgMaxTilingData {
    uint64_t outputLength;
    uint64_t blockLength;
    uint64_t reduceLength;
    uint64_t innerLength;
    uint32_t blockNum;
    uint32_t dtype;
};

inline ArgMaxTilingData ComputeArgMaxTiling(
    const std::vector<uint64_t> &shape, int64_t dim, uint32_t dtype, int64_t cores) {
    if (shape.empty() || shape.size() > 8) throw std::invalid_argument("rank must be in [1, 8]");
    if (dim < 0) dim += static_cast<int64_t>(shape.size());
    if (dim < 0 || dim >= static_cast<int64_t>(shape.size())) throw std::invalid_argument("dim out of range");
    if (shape[dim] == 0) throw std::invalid_argument("argmax reduction dimension must be non-empty");
    ArgMaxTilingData t{};
    t.reduceLength = shape[dim];
    t.innerLength = 1;
    uint64_t outerLength = 1;
    for (int64_t i = 0; i < dim; ++i) outerLength *= shape[i];
    for (size_t i = static_cast<size_t>(dim + 1); i < shape.size(); ++i) t.innerLength *= shape[i];
    t.outputLength = outerLength * t.innerLength;
    t.dtype = dtype;
    t.blockNum = static_cast<uint32_t>(std::max<int64_t>(
        1, std::min<int64_t>(cores, static_cast<int64_t>(t.outputLength))));
    // Scalar int64 GM stores are serviced at a wider cache-line granularity.
    // Keep every core boundary 64-byte aligned so adjacent cores never perform
    // read-modify-write traffic on the same output cache line.
    const uint64_t average = (t.outputLength + t.blockNum - 1) / t.blockNum;
    t.blockLength = ((average + 7U) / 8U) * 8U;
    return t;
}
