#pragma once
#include <algorithm>
#include <cstdint>
#include <stdexcept>
#include <vector>

enum GridSamplerDType : uint32_t { GRID_FP16 = 0, GRID_FP32 = 1 };
enum GridSamplerInterpolation : uint32_t { GRID_BILINEAR = 0, GRID_NEAREST = 1 };
enum GridSamplerPadding : uint32_t { GRID_ZEROS = 0, GRID_BORDER = 1, GRID_REFLECTION = 2 };

struct GridSampler3DTilingData {
    uint64_t n, c, d, h, w;
    uint64_t outD, outH, outW;
    uint64_t spatialOut, outputNumel;
    uint64_t blockLength;
    float dFloat, hFloat, wFloat;
    uint32_t blockNum;
    uint32_t dtype;
    uint32_t interpolation;
    uint32_t padding;
    uint32_t alignCorners;
};

inline GridSampler3DTilingData ComputeGridSampler3DTiling(
    const std::vector<uint64_t> &x, const std::vector<uint64_t> &grid,
    uint32_t dtype, uint32_t interpolation, uint32_t padding,
    bool alignCorners, int64_t cores) {
    if (x.size() != 5 || grid.size() != 5 || grid[4] != 3 || x[0] != grid[0])
        throw std::invalid_argument("expected x[N,C,D,H,W], grid[N,Do,Ho,Wo,3] with matching N");
    for (uint64_t v : x) if (v == 0) throw std::invalid_argument("zero dimensions are unsupported");
    for (uint64_t v : grid) if (v == 0) throw std::invalid_argument("zero dimensions are unsupported");
    GridSampler3DTilingData t{};
    t.n=x[0]; t.c=x[1]; t.d=x[2]; t.h=x[3]; t.w=x[4];
    t.dFloat=static_cast<float>(t.d); t.hFloat=static_cast<float>(t.h); t.wFloat=static_cast<float>(t.w);
    t.outD=grid[1]; t.outH=grid[2]; t.outW=grid[3];
    t.spatialOut=t.outD*t.outH*t.outW;
    t.outputNumel=t.n*t.c*t.spatialOut;
    t.dtype=dtype; t.interpolation=interpolation; t.padding=padding;
    t.alignCorners=alignCorners ? 1U : 0U;
    const uint64_t available=static_cast<uint64_t>(std::max<int64_t>(1, cores));
    const uint64_t alignment=dtype == GRID_FP16 ? 32 : 16; // 64-byte GM ownership boundary.
    const uint64_t useful=std::max<uint64_t>(1, (t.outputNumel + alignment - 1) / alignment);
    t.blockNum=static_cast<uint32_t>(std::min<uint64_t>(available, useful));
    const uint64_t raw=(t.outputNumel + t.blockNum - 1) / t.blockNum;
    t.blockLength=((raw + alignment - 1) / alignment) * alignment;
    return t;
}
