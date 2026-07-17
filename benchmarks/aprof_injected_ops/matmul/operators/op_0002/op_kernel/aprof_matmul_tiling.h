#ifndef APROF_MATMUL_TILING_H
#define APROF_MATMUL_TILING_H
#include <cstdint>
struct AprofMatmulTilingData {
    uint32_t m, n, k;
    uint32_t tileM, tileN, tileMAligned, tileNAligned;
    uint32_t rowsPerCore;
    uint32_t inputStride, outputStride;
    uint32_t blockdim, variantFlags;
};
#endif
