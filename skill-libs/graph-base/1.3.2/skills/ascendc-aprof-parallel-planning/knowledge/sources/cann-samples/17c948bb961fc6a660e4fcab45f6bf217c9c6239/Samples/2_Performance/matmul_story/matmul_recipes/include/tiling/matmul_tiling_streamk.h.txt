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
 * \file matmul_tiling_streamk.h
 * \brief StreamK tiling specialization for .
 */

#pragma once

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include "tiling/matmul_tiling_base.h"
#include "host_utils/common_utils.h"

class MatmulTilingStreamK : public MatmulTilingBase {
public:
    MatmulTilingStreamK() = default;
    ~MatmulTilingStreamK() override = default;

protected:
    const char* TilingName() const override
    {
        return "streamk";
    }

    void DoOpTiling(MatmulTilingData& tilingData) override
    {
        IsCapable();
        ResetBase();
        FormulateBasicBlock();
        CalBaseK();
        CalL1Tiling();
        AdjustL1Tiling();
        BuildTilingData(tilingData);
    }

private:
    uint64_t mCnt_{1};
    uint64_t nCnt_{1};
    uint64_t totalMNCnt_{1};

    size_t GetWorkSpace() override
    {
        return platformInfo_.aicNum * BASIC_BLOCK_SIZE_256 * BASIC_BLOCK_SIZE_256 * DATA_SIZE_FP32 +
               RPC_WORKSIZE * MB_SIZE;
    }

    void IsCapable()
    {
        // Check whether it meets SK or DPSK
        bool isCapable = CheckStreamKSKTiling() || CheckStreamKDPSKTiling();
        CHECK_COND(isCapable, "The requested streamK tiling does not support the current shape");
    }

    bool CheckStreamKSKTiling()
    {
        constexpr uint64_t STREAM_K_MIN_K_THRESHOLD = 8192UL;
        uint64_t kThreshold =
            std::max(STREAM_K_MIN_K_THRESHOLD, platformInfo_.aicNum * BASIC_BLOCK_SIZE_256) / args_.dataTypeSize;
        if (Align(args_.k, BASIC_BLOCK_SIZE_256) < kThreshold) {
            return false;
        }
        uint64_t alignValue = BASIC_BLOCK_SIZE_256;
        if (args_.dataTypeSize == DATA_SIZE_FP32 && !args_.isHf32) {
            alignValue = BLOCK_BYTE_SIZE;
        }
        uint64_t mCnt = CeilDiv(args_.m, alignValue);
        uint64_t nCnt = CeilDiv(args_.n, alignValue);
        return (mCnt * nCnt <= platformInfo_.aicNum / NUM_TWO);
    }

    bool CheckStreamKDPSKTiling()
    {
        constexpr uint64_t STREAM_K_MIN_K_THRESHOLD = 8192UL;
        if (args_.m % BASIC_BLOCK_SIZE_256 != 0UL || args_.n % BASIC_BLOCK_SIZE_256 != 0UL) {
            return false;
        }
        uint64_t kThreshold =
            std::max(STREAM_K_MIN_K_THRESHOLD, platformInfo_.aicNum * BASIC_BLOCK_SIZE_128) / args_.dataTypeSize;
        if (args_.k < kThreshold) {
            return false;
        }
        uint64_t mCnt = CeilDiv(args_.m, BASIC_BLOCK_SIZE_256);
        uint64_t nCnt = CeilDiv(args_.n, BASIC_BLOCK_SIZE_256);
        uint64_t totalMNCnt = mCnt * nCnt;
        return (totalMNCnt >= platformInfo_.aicNum) && (totalMNCnt % platformInfo_.aicNum != 0UL) &&
               (totalMNCnt % platformInfo_.aicNum <= platformInfo_.aicNum / NUM_TWO);
    }

    void ResetBase()
    {
        runInfo_.usedCoreNum = platformInfo_.aicNum;
        runInfo_.baseM = BASIC_BLOCK_SIZE_256;
        runInfo_.baseN = BASIC_BLOCK_SIZE_256;
        runInfo_.baseK = BASIC_BLOCK_SIZE_128 / args_.dataTypeSize;
        runInfo_.stepM = 1;
        runInfo_.stepN = 1;
        runInfo_.iterateOrder = 0;
        runInfo_.dbL0c = 1;
        runInfo_.singleCoreK = args_.k;
        runInfo_.singleCoreM = runInfo_.baseM;
        runInfo_.singleCoreN = runInfo_.baseN;
        runInfo_.mBaseTailSplitCnt = 1;
        runInfo_.nBaseTailSplitCnt = 1;
        runInfo_.tailInfo.mTailMain = 0;
        runInfo_.tailInfo.nTailMain = 0;
    }

    void FormulateBasicBlock()
    {
        mCnt_ = CeilDiv(args_.m, runInfo_.baseM);
        nCnt_ = CeilDiv(args_.n, runInfo_.baseN);
        totalMNCnt_ = mCnt_ * nCnt_;

        if (totalMNCnt_ <= platformInfo_.aicNum / NUM_TWO) {
            if (mCnt_ > platformInfo_.aicNum / NUM_THREE && mCnt_ < platformInfo_.aicNum / NUM_TWO) {
                mCnt_ = platformInfo_.aicNum / NUM_TWO;
            }
            if (nCnt_ > platformInfo_.aicNum / NUM_THREE && nCnt_ < platformInfo_.aicNum / NUM_TWO) {
                nCnt_ = platformInfo_.aicNum / NUM_TWO;
            }
            totalMNCnt_ = mCnt_ * nCnt_;
            runInfo_.baseM = Align(CeilDiv(args_.m, mCnt_), BASIC_BLOCK_SIZE_16);
            runInfo_.baseN = Align(CeilDiv(args_.n, nCnt_), BASIC_BLOCK_SIZE_16);
            runInfo_.tailInfo.kCnt = platformInfo_.aicNum / totalMNCnt_;
            runInfo_.singleCoreK = CeilDiv(args_.k, runInfo_.tailInfo.kCnt);
        } else {
            runInfo_.tailInfo.kCnt = platformInfo_.aicNum / (totalMNCnt_ % platformInfo_.aicNum);
            uint64_t skSingleCoreK = CeilDiv(args_.k, runInfo_.tailInfo.kCnt);
            runInfo_.tailInfo.kCnt = CeilDiv(args_.k, skSingleCoreK);
            runInfo_.singleCoreK = skSingleCoreK;
        }
    }

    void CalBaseK()
    {
        uint64_t baseKAlignValue =
            (!args_.isATrans || args_.isBTrans) ? BASIC_BLOCK_SIZE_128 / args_.dataTypeSize : BASIC_BLOCK_SIZE_16;
        uint64_t kValueMax = FloorAlign(
            platformInfo_.l0aSize / DB_SIZE / args_.dataTypeSize / std::max(runInfo_.baseM, runInfo_.baseN),
            baseKAlignValue);
        runInfo_.baseK = std::min(runInfo_.singleCoreK, kValueMax);
    }

    void CalL1Tiling()
    {
        uint64_t totalL1Size = platformInfo_.l1Size;
        uint64_t reserveBTSize = args_.hasBias ? BASIC_BLOCK_SIZE_256 * DATA_SIZE_FP32 : 0UL;
        runInfo_.depthA1 = totalL1Size / NUM_TWO / runInfo_.baseM / runInfo_.baseK / args_.dataTypeSize; // 2: half of l1
        runInfo_.depthB1 = totalL1Size / NUM_TWO / runInfo_.baseN / runInfo_.baseK / args_.dataTypeSize; // 2: half of l1

        uint64_t depthASize = runInfo_.depthA1 * runInfo_.baseM * runInfo_.baseK * args_.dataTypeSize;
        uint64_t depthBSize = runInfo_.depthB1 * runInfo_.baseN * runInfo_.baseK * args_.dataTypeSize;
        if (depthASize + depthBSize > totalL1Size - reserveBTSize) {
            if (runInfo_.baseM <= runInfo_.baseN) {
                runInfo_.depthA1 = std::max(runInfo_.depthA1 / NUM_TWO, 1UL); // 2: adjust deptch for l1 buffer
            } else {
                runInfo_.depthB1 = std::max(runInfo_.depthB1 / NUM_TWO, 1UL); // 2: adjust deptch for l1 buffer
            }
        }
        runInfo_.stepKa = std::max(runInfo_.depthA1 / DB_SIZE, 1UL);
        runInfo_.stepKb = std::max(runInfo_.depthB1 / DB_SIZE, 1UL);

        // When aligned and base block is [256, 256], adjust stepK
        if (runInfo_.baseM == BASIC_BLOCK_SIZE_256 && runInfo_.baseN == BASIC_BLOCK_SIZE_256 &&
            args_.m % BASIC_BLOCK_SIZE_16 == 0 && args_.n % BASIC_BLOCK_SIZE_16 == 0 &&
            args_.k % BASIC_BLOCK_SIZE_16 == 0 && runInfo_.singleCoreK <= BASIC_BLOCK_SIZE_256) {
            runInfo_.stepKa = std::min(runInfo_.stepKa, 2UL);
            runInfo_.stepKb = std::min(runInfo_.stepKb, 2UL);
        }

        // Adjust stepKa and stepKb to be integer multiples of each other
        if (runInfo_.stepKa >= runInfo_.stepKb) {
            runInfo_.stepKa = runInfo_.stepKa / runInfo_.stepKb * runInfo_.stepKb;
        } else {
            runInfo_.stepKb = runInfo_.stepKb / runInfo_.stepKa * runInfo_.stepKa;
        }

        // Enable double buffer by default
        runInfo_.depthA1 = runInfo_.stepKa * DB_SIZE; // depth % (stepKa * stepM) == 0
        runInfo_.depthB1 = runInfo_.stepKb * DB_SIZE; // depth % (stepKb * stepN) == 0
        runInfo_.singleCoreM = runInfo_.baseM;
        runInfo_.singleCoreN = runInfo_.baseN;
        return;
    }

    void AdjustL1Tiling()
    {
        // DepthB1 is less than depthA1
        if (runInfo_.baseM == runInfo_.baseN && runInfo_.depthB1 == runInfo_.depthA1 * NUM_TWO) {
            runInfo_.depthA1 = runInfo_.depthA1 * NUM_TWO;
            runInfo_.depthB1 = runInfo_.depthB1 / NUM_TWO;
            runInfo_.stepKb = runInfo_.depthB1 / DB_SIZE;
            runInfo_.stepKa = runInfo_.depthA1 / DB_SIZE;
        }
        // Reserve L1 space for bias
        if ((totalMNCnt_ > platformInfo_.aicNum) && args_.hasBias) {
            runInfo_.stepKb = NUM_THREE;
            runInfo_.stepKa = NUM_THREE;
        }
    }

    void BuildTilingData(MatmulTilingData& tilingData) const
    {
        tilingData = {};
        tilingData.m = static_cast<uint32_t>(args_.m);
        tilingData.n = static_cast<uint32_t>(args_.n);
        tilingData.k = static_cast<uint32_t>(args_.k);
        tilingData.baseM = static_cast<uint32_t>(runInfo_.baseM);
        tilingData.baseN = static_cast<uint32_t>(runInfo_.baseN);
        tilingData.baseK = static_cast<uint32_t>(runInfo_.baseK);
        tilingData.skSingleCoreK = static_cast<uint32_t>(runInfo_.singleCoreK);
        tilingData.mL1 = std::min(Align(args_.m, BASIC_BLOCK_SIZE_16), runInfo_.baseM);
        tilingData.nL1 = std::min(Align(args_.n, BASIC_BLOCK_SIZE_16), runInfo_.baseN);
        int32_t stepKa = std::min(runInfo_.stepKb, runInfo_.stepKa);
        int32_t STEPKA_THRESHOLD = 4;
        stepKa = std::min(STEPKA_THRESHOLD, stepKa);
        tilingData.kL1 = runInfo_.baseK * static_cast<uint32_t>(stepKa);
        tilingData.mTailCnt = static_cast<uint32_t>(runInfo_.tailInfo.mCnt);
        tilingData.nTailCnt = static_cast<uint32_t>(runInfo_.tailInfo.nCnt);
        tilingData.mBaseTailSplitCnt = runInfo_.mBaseTailSplitCnt;
        tilingData.nBaseTailSplitCnt = runInfo_.nBaseTailSplitCnt;
        tilingData.mTailMain = runInfo_.tailInfo.mTailMain;
        tilingData.nTailMain = runInfo_.tailInfo.nTailMain;
        tilingData.usedCoreNum = static_cast<uint32_t>(runInfo_.usedCoreNum);
        tilingData.isHf32 = args_.isHf32;
        tilingData.l1BufferNum = static_cast<uint8_t>(runInfo_.l1BufferNum);
        tilingData.l0cDB = static_cast<uint8_t>(runInfo_.dbL0c);
    }
};
