#ifndef APROF_FOREACH_TILING_H
#define APROF_FOREACH_TILING_H

#include <cstdint>

// feature toggle block
struct AprofForeachTilingData {
    uint32_t numTensors;       // total tensors in the input list
    uint32_t tensorLength;     // elements per tensor
    uint32_t tileLength;       // inner reduction tile
    uint32_t tileLengthAligned;
    uint32_t tensorsPerCore;   // tensors assigned to this core
    uint32_t inputStride;      // N * tensorLength (aligned)
    uint32_t outputStride;     // N (aligned)
    uint32_t blockdim;         // launch blockdim
    uint32_t variantFlags;
};

#endif // APROF_FOREACH_TILING_H
