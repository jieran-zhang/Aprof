#pragma once
#include <cstdint>
enum DequantSwigluDtype : uint32_t { DSQ_FP16=0, DSQ_BF16=1, DSQ_INT32=2 };
struct DequantSwigluTilingData {
  uint64_t rows;
  uint32_t half;
  uint32_t dtype;
  uint32_t hasQuantScale;
  uint32_t activateLeft;
  uint32_t blockRows;
  uint32_t blockNum;
};
inline DequantSwigluTilingData ComputeDequantSwigluTiling(uint64_t rows, uint32_t half,
    uint32_t dtype, bool hasQuantScale, bool activateLeft, int64_t cores) {
  DequantSwigluTilingData t{}; t.rows=rows;t.half=half;t.dtype=dtype;
  t.hasQuantScale=hasQuantScale;t.activateLeft=activateLeft;
  t.blockNum=static_cast<uint32_t>(rows < static_cast<uint64_t>(cores) ? rows : cores);
  if(t.blockNum==0)t.blockNum=1;t.blockRows=static_cast<uint32_t>((rows+t.blockNum-1)/t.blockNum);return t;
}
