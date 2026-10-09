#pragma once
#include <algorithm>
#include <cstdint>
#include <stdexcept>
#include <vector>

enum ScatterDataType : uint32_t {
    SCATTER_FLOAT16 = 0,
    SCATTER_FLOAT32 = 1,
    SCATTER_BFLOAT16 = 2,
    SCATTER_INT32 = 3,
    SCATTER_INT64 = 4,
};
enum ScatterIndexType : uint32_t { SCATTER_INDEX_INT32 = 0, SCATTER_INDEX_INT64 = 1 };
enum ScatterReduce : uint32_t {
    SCATTER_UPDATE = 0,
    SCATTER_ADD = 1,
    SCATTER_MULTIPLY = 2,
    SCATTER_AMIN = 3,
    SCATTER_AMAX = 4,
};

struct ScatterTilingData {
    uint64_t dataLength;
    uint64_t updateLength;
    uint64_t dataStride[8];
    uint64_t updateShape[8];
    uint32_t rank;
    uint32_t dim;
    uint32_t dataType;
    uint32_t indexType;
    uint32_t reduce;
    uint32_t convertBlockNum;
    uint64_t convertBlockLength;
};

inline uint64_t ScatterNumel(const std::vector<uint64_t> &shape) {
    uint64_t n = 1;
    for (uint64_t d : shape) n *= d;
    return n;
}

inline ScatterTilingData ComputeScatterTiling(
    const std::vector<uint64_t> &dataShape,
    const std::vector<uint64_t> &indexShape,
    int64_t dim, uint32_t dataType, uint32_t indexType, uint32_t reduce) {
    if (dataShape.empty() || dataShape.size() > 8 || dataShape.size() != indexShape.size())
        throw std::invalid_argument("data and indices ranks must match and be in [1, 8]");
    const int64_t rank = static_cast<int64_t>(dataShape.size());
    if (dim < 0) dim += rank;
    if (dim < 0 || dim >= rank) throw std::invalid_argument("dim is out of range");
    ScatterTilingData t{};
    t.rank = static_cast<uint32_t>(rank);
    t.dim = static_cast<uint32_t>(dim);
    t.dataType = dataType;
    t.indexType = indexType;
    t.reduce = reduce;
    t.convertBlockNum = 32;
    uint64_t stride = 1;
    for (int64_t i = rank - 1; i >= 0; --i) {
        if (indexShape[i] > dataShape[i])
            throw std::invalid_argument("indices dimension exceeds data dimension");
        t.dataStride[i] = stride;
        t.updateShape[i] = indexShape[i];
        stride *= dataShape[i];
    }
    t.dataLength = stride;
    t.updateLength = ScatterNumel(indexShape);
    t.convertBlockLength = (t.dataLength + t.convertBlockNum - 1) / t.convertBlockNum;
    return t;
}
