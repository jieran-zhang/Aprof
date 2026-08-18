#pragma once
#include <algorithm>
#include <cstdint>
#include <stdexcept>

enum MoeFinalizeDtype : uint32_t { MFR_FLOAT16 = 0, MFR_FLOAT32 = 1, MFR_BFLOAT16 = 2 };
struct MoeFinalizeTilingData {
    uint64_t rows, hidden, nk, expandedRows, outputNumel, blockLength;
    uint32_t k, experts, dtype, scaleDtype, blockNum, dropPadMode;
    uint32_t hasSkip1, hasSkip2, hasBias, hasScales, hasExperts;
};
inline MoeFinalizeTilingData ComputeMoeFinalizeTiling(uint64_t rows, uint64_t hidden,
    uint64_t nk, uint64_t expandedRows, uint32_t k, uint32_t experts, uint32_t dtype,
    uint32_t scaleDtype, uint32_t mode, bool skip1, bool skip2, bool bias, bool scales,
    bool expertIds, int64_t cores) {
    if (!rows || !hidden || !nk || !expandedRows || !k || nk != rows * k) throw std::invalid_argument("invalid shape relationship");
    if (mode > 3) throw std::invalid_argument("drop_pad_mode must be in [0,3]");
    if (skip2 && !skip1) throw std::invalid_argument("skip2 requires skip1");
    if (bias && !expertIds) throw std::invalid_argument("bias requires expert ids");
    MoeFinalizeTilingData t{}; t.rows=rows; t.hidden=hidden; t.nk=nk; t.expandedRows=expandedRows;
    t.outputNumel=rows*hidden; t.k=k; t.experts=experts; t.dtype=dtype; t.scaleDtype=scaleDtype;
    t.dropPadMode=mode; t.hasSkip1=skip1; t.hasSkip2=skip2; t.hasBias=bias; t.hasScales=scales; t.hasExperts=expertIds;
    t.blockNum=std::max<uint32_t>(1,std::min<uint64_t>(std::max<int64_t>(1,cores),t.outputNumel));
    uint64_t raw=(t.outputNumel+t.blockNum-1)/t.blockNum; t.blockLength=((raw+127)/128)*128; return t;
}
