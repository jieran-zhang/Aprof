#ifndef APROF_VECTOR_TILING_H
#define APROF_VECTOR_TILING_H

#include <cstdint>

struct AprofVectorTilingData {
    uint32_t inputElements;
    uint32_t outputElements;
    uint32_t inputStride;
    uint32_t outputStride;
    uint32_t elemsPerCore;
    uint32_t tileLength;
    uint32_t tileLengthAligned;
    uint32_t tileNum;
    uint32_t tailLength;
    uint32_t variantFlags;
};

#endif // APROF_VECTOR_TILING_H
