/**
 * Copyright (c) 2026 Huawei Technologies Co., Ltd.
 * This program is free software, you can redistribute it and/or modify it under the terms and conditions of
 * CANN Open Software License Agreement Version 2.0 (the "License").
 * Please refer to the License for details. You may not use this file except in compliance with the License.
 * THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
 * INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
 * See LICENSE in the root of the software repository for the full text of the License.
 */

/*!
 * \file matmul_block_scheduler_streamk.h
 * \brief StreamK block scheduler for  implementation.
 */

#pragma once

#include "kernel_utils/common_utils.h"
#include "utils/constant.h"
#include "tiling/matmul_tiling_data.h"
#include "./block_scheduler_utils.h"

namespace Block {

template <class ProblemShape_>
class BlockSchedulerStreamK {
public:
    int64_t usedCoreNum_{0};
    int64_t mTileNum_{0};
    int64_t nTileNum_{0};
    int64_t skKTileNum_{0};
    int64_t tileNum_{1};
    int64_t totalMNTileNumInDP_{0};

    int64_t batch_{0};
    int64_t m_{0};
    int64_t n_{0};
    int64_t k_{0};

    int64_t mTileIdx_{1};
    int64_t nTileIdx_{1};
    int64_t kTileIdx_{1};
    int64_t curKTileNum_{1};

    int64_t mL1_{0};
    int64_t nL1_{0};
    int64_t kL1_{0};
    int64_t skKSingleCore_{0};
    int64_t baseM_{0};
    int64_t baseN_{0};
    int64_t baseK_{0};

    static constexpr uint64_t WINDOW_LEN = 4UL;
    using BlockShape = AscendC::Shape<int64_t, int64_t, int64_t, int64_t>;
    using BlockCoord = AscendC::Coord<int64_t, int64_t, int64_t, int64_t>;
    using ProblemShape = ProblemShape_;

    struct Params {
        int64_t usedCoreNum;
        int64_t baseM;
        int64_t baseN;
        int64_t baseK;
        int64_t kL1;
        int64_t skSingleCoreK;
    };

public:
    __aicore__ inline BlockSchedulerStreamK(const ProblemShape& shape, const Params& params)
    {
        usedCoreNum_ = params.usedCoreNum;
        m_ = shape.m;
        n_ = shape.n;
        k_ = shape.k;
        batch_ = AscendC::Std::max(shape.b, 1L);
        baseM_ = params.baseM;
        baseN_ = params.baseN;
        mL1_ = baseM_; // size of m in L1 & L0 & singlecore, per core use L1 once in stream k
        nL1_ = baseN_; // size of n in L1 & L0 & singlecore, per core use L1 once in stream k

        skKSingleCore_ = params.skSingleCoreK; // size of k in singlecore
        baseK_ = params.baseK;                 // fix basek to 32, need to be adjusted by baseM, baseN, L0
        kL1_ = params.kL1;

        mTileNum_ = CeilDiv(shape.m, mL1_);
        nTileNum_ = CeilDiv(shape.n, nL1_);
        skKTileNum_ = CeilDiv(k_, skKSingleCore_);

        int64_t tailMNTileNum = (mTileNum_ * nTileNum_) % usedCoreNum_; // tail mCnt * nCnt num of SK
        // totaltilenum = core num of DP (m*n) + tail core num of SK (m*n*k)
        tileNum_ = (mTileNum_ * nTileNum_ - tailMNTileNum) + tailMNTileNum * skKTileNum_;
        totalMNTileNumInDP_ = mTileNum_ * nTileNum_ - tailMNTileNum;
    }

    __aicore__ inline int64_t GetTotalTileNum()
    {
        return tileNum_ * batch_;
    }

    __aicore__ inline Shape<int64_t, int64_t, int64_t, int64_t> GetMNKTileNum()
    {
        return {mTileNum_, nTileNum_, skKTileNum_, 1};
    }

    __aicore__ inline int64_t GetCurKSingleCore(int64_t tileIdx)
    {
        return (CheckIsSkScene(tileIdx) ? skKSingleCore_ : k_);
    }

    __aicore__ inline int64_t GetBlockNum(int64_t blockNum)
    {
        int64_t tilingBlockNum = 0;
        if (tileNum_ * batch_ < blockNum) {
            tilingBlockNum = tileNum_ * batch_;
        } else {
            tilingBlockNum = blockNum;
        }
        return tilingBlockNum;
    }

    __aicore__ inline Shape<int64_t, int64_t, int64_t, int64_t> GetTileL0Shape()
    {
        return {baseM_, baseN_, baseK_, 1};
    }

    __aicore__ inline BlockShape GetSingleCoreShape(int64_t tileIdx)
    {
        UpdateMNTileIdx(tileIdx);
        int64_t tailL1M = m_ - (mTileNum_ - 1) * mL1_;
        int64_t tailL1N = n_ - (nTileNum_ - 1) * nL1_;
        int64_t tailSingleCoreK = k_ - (curKTileNum_ - 1) * skKSingleCore_;
        int64_t blkM = (mTileIdx_ == (mTileNum_ - 1)) ? tailL1M : mL1_;
        int64_t blkN = (nTileIdx_ == (nTileNum_ - 1)) ? tailL1N : nL1_;
        int64_t blkK = (kTileIdx_ == (curKTileNum_ - 1)) ? tailSingleCoreK : skKSingleCore_;
        return {blkM, blkN, blkK, 0};
    }

    __aicore__ inline BlockCoord GetSingleCoreCoord(int64_t tileIdx)
    {
        UpdateMNTileIdx(tileIdx);
        return {mTileIdx_, nTileIdx_, kTileIdx_, 0};
    }

    __aicore__ inline bool CheckIsSkScene(int64_t tileIdx)
    {
        return CeilDiv((tileIdx + 1), usedCoreNum_) == CeilDiv(tileNum_, usedCoreNum_); // true is sk, false is dp
    }

private:
    __aicore__ inline void UpdateMNTileIdx(int64_t tileIdx)
    {
        // judge now in dp loop (kTileNum = 1) or in sk loop
        curKTileNum_ = CheckIsSkScene(tileIdx) ? skKTileNum_ : 1;
        int64_t mnIdxInCurLoop = 0;
        if (CheckIsSkScene(tileIdx)) { // SK scene
            kTileIdx_ = (tileIdx % usedCoreNum_) % curKTileNum_;
            mnIdxInCurLoop = (tileIdx % usedCoreNum_) / curKTileNum_ + totalMNTileNumInDP_;
        } else { // DP scene
            kTileIdx_ = 0;
            mnIdxInCurLoop = tileIdx / curKTileNum_;
        }
        int64_t mainWindow = AscendC::Std::min(WINDOW_LEN, mTileNum_);
        int64_t mainRow = mTileNum_ / mainWindow - 1UL;
        int64_t tailWindow = mTileNum_ - mainRow * mainWindow;
        int64_t rowIdx = mnIdxInCurLoop / nTileNum_ / mainWindow;
        if (rowIdx < mainRow) {
            mTileIdx_ = rowIdx * mainWindow + mnIdxInCurLoop % mainWindow;
            nTileIdx_ = (mnIdxInCurLoop / mainWindow) % nTileNum_;
        } else {
            rowIdx = mainRow;
            int64_t tailIndex = mnIdxInCurLoop - mainRow * mainWindow * nTileNum_;
            mTileIdx_ = mainRow * mainWindow + tailIndex % tailWindow;
            nTileIdx_ = (tailIndex / tailWindow) % nTileNum_;
        }
        // mod 2 means even row, need reverse scan
        if (rowIdx % 2 != 0UL) {
            nTileIdx_ = nTileNum_ - 1UL - nTileIdx_;
        }
    }
};

template <class ProblemShape_, bool TransA_, bool TransB_>
struct BlockSchedulerSelector<ProblemShape_, MatmulStreamKScheduler, TransA_, TransB_> {
    using SchedulerOp = BlockSchedulerStreamK<ProblemShape_>;
};

} // namespace Block
