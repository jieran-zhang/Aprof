#pragma once
#include <algorithm>
#include <cstdint>
#include <stdexcept>
#include <vector>
#include "tiling/tiling_api.h"

enum SoftmaxDType : uint32_t {
    SOFTMAX_FLOAT16 = 0,
    SOFTMAX_FLOAT32 = 1,
    SOFTMAX_BFLOAT16 = 2,
};

struct SoftmaxTilingData {
    uint64_t outerLength;
    uint64_t reduceLength;
    uint64_t innerLength;
    uint64_t sliceCount;
    uint64_t blockLength;
    uint32_t blockNum;
    uint32_t dtype;
    uint32_t alignedReduce;
    uint32_t workspaceBytes;
    SoftMaxTiling softmaxTiling;
};

inline uint64_t SoftmaxGcd(uint64_t a, uint64_t b) {
    while (b != 0) { const uint64_t r = a % b; a = b; b = r; }
    return a;
}

inline SoftmaxTilingData ComputeSoftmaxTiling(
    const std::vector<uint64_t> &shape, int64_t dim, uint32_t dtype, int64_t cores) {
    if (shape.empty() || shape.size() > 8) throw std::invalid_argument("rank must be in [1, 8]");
    if (dim < 0) dim += static_cast<int64_t>(shape.size());
    if (dim < 0 || dim >= static_cast<int64_t>(shape.size())) throw std::invalid_argument("dim out of range");
    SoftmaxTilingData t{};
    t.outerLength = 1; t.innerLength = 1; t.reduceLength = shape[dim]; t.dtype = dtype;
    if (t.reduceLength == 0 || t.reduceLength > 16384) throw std::invalid_argument("reduction dimension must be in [1, 16384]");
    for (int64_t i = 0; i < dim; ++i) t.outerLength *= shape[i];
    for (size_t i = static_cast<size_t>(dim + 1); i < shape.size(); ++i) t.innerLength *= shape[i];
    t.sliceCount = t.outerLength * t.innerLength;
    const uint32_t apiElementsPerBlock = dtype == SOFTMAX_FLOAT16 ? 64U
        : (dtype == SOFTMAX_BFLOAT16 ? 16U : 8U);
    t.alignedReduce = static_cast<uint32_t>(
        ((t.reduceLength + apiElementsPerBlock - 1U) / apiElementsPerBlock) * apiElementsPerBlock);
    t.workspaceBytes = 61440;
    ge::Shape computeShape({1, static_cast<int64_t>(t.alignedReduce)});
    const uint32_t apiTypeBytes = dtype == SOFTMAX_FLOAT16 ? sizeof(uint16_t) : sizeof(float);
    AscendC::SoftMaxTilingFunc(computeShape, apiTypeBytes, t.workspaceBytes, t.softmaxTiling);
    t.blockNum = static_cast<uint32_t>(std::max<int64_t>(
        1, std::min<int64_t>(cores, static_cast<int64_t>(t.sliceCount))));
    const uint64_t average = (t.sliceCount + t.blockNum - 1) / t.blockNum;
    const uint64_t itemBytes = dtype == SOFTMAX_FLOAT32 ? 4 : 2;
    const uint64_t alignment = 64 / SoftmaxGcd(t.reduceLength * itemBytes, 64);
    t.blockLength = ((average + alignment - 1) / alignment) * alignment;
    return t;
}
