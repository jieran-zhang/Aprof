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
 * \file matmul_block_epilogue_streamk.h
 * \brief Block-level  accumulation operation in the Vector Core for StreamK path.
 */

#pragma once

#if ASC_DEVKIT_MAJOR >= 9
#include "kernel_basic_intf.h"
#else
#include "kernel_operator.h"
#endif
#include "kernel_utils/common_utils.h"

namespace Block {

template <class WorkspaceType, class OutType>
class BlockEpilogueStreamK {
public:
    using TupleShape = Shape<int64_t, int64_t, int64_t>;
    using BlockCoord = Coord<int64_t, int64_t, int64_t, int64_t>;

    struct Arguments {
        GM_ADDR cGmAddr{nullptr};
        GM_ADDR workspaceGmAddr{nullptr};
    };

    using Params = Arguments;

    __aicore__ inline BlockEpilogueStreamK()
    {}
    __aicore__ inline ~BlockEpilogueStreamK()
    {}

    AscendC::GlobalTensor<OutType> cGlobal_;
    AscendC::GlobalTensor<WorkspaceType> workspaceGlobal_;

    // basic args
    uint64_t m_ = 0;
    uint64_t n_ = 0;
    uint64_t mL1_ = 0;
    uint64_t nL1_ = 0;
    uint64_t mCnt_ = 0;
    uint64_t nCnt_ = 0;
    uint64_t kCnt_ = 0;
    uint64_t round_ = 1;
    uint64_t usedCoreNum_ = 0;
    uint64_t aivMte2Num_ = 0;

    struct AivParams {
        uint64_t indexParams = 0;
        uint64_t mCntIndex = 0;
        uint64_t nCntIndex = 0;
        uint64_t kCntIndex = 0;
        uint64_t curML1InAiv = 0;
        uint64_t curNL1InAiv = 0;
        uint64_t curAlignedNInAiv = 0;
    };
    AivParams aivParams_;

    uint64_t mBurstBase_ = 0;

    struct CopyGm2UbParams {
        uint64_t offsetWorkspaceGM = 0;
        uint64_t kCnt = 0;
        uint64_t mBurstOri = 0;
        uint64_t mBurst = 0;
        uint64_t burstLen = 0;
        uint64_t srcGap = 0;
    };
    CopyGm2UbParams copyGm2UbParams_;

    struct CopyUb2GmParams {
        uint64_t offsetCGm = 0;
        uint64_t mLength = 0;
        uint64_t burstLen = 0;
        uint64_t dstGap = 0;
        uint64_t srcGap = 0;
    };
    CopyUb2GmParams copyUb2GmParams_;

    __aicore__ inline void Init(
        Params const& params, TupleShape blockShapeInAiv, TupleShape tileL1ShapeInAiv, BlockCoord coordInAiv,
        uint64_t usedCoreNum, bool checkIsSkScene)
    {
        m_ = asc::te::get<MNK_M>(blockShapeInAiv);
        n_ = asc::te::get<MNK_N>(blockShapeInAiv);
        mL1_ = asc::te::get<MNK_M>(tileL1ShapeInAiv);
        nL1_ = asc::te::get<MNK_N>(tileL1ShapeInAiv);
        mCnt_ = asc::te::get<MNK_M>(coordInAiv);
        nCnt_ = asc::te::get<MNK_N>(coordInAiv);
        kCnt_ = asc::te::get<MNK_K>(coordInAiv);
        usedCoreNum_ = usedCoreNum;
        // Decrease tile size of per vector core to prevent data race of cube and vector
        aivMte2Num_ = checkIsSkScene ? AscendC::GetTaskRatio() : AscendC::BLOCK_CUBE;
        cGlobal_.SetGlobalBuffer(reinterpret_cast<__gm__ OutType*>(params.cGmAddr));
        workspaceGlobal_.SetGlobalBuffer(reinterpret_cast<__gm__ WorkspaceType*>(params.workspaceGmAddr));
        ICachePreLoad(NUM_TWO);
        // Ensure cube to pair with vector, add sync flag in dp+sk scene
        // ISASI: MTE3<->MTE2 紧邻单发用函数级局部 mutex 保守表达，Init 末 Release。
        if (!checkIsSkScene) {
            uint8_t syncMutex = AscendC::AllocMutexID();
            AscendC::Mutex::Lock<PIPE_MTE3>(syncMutex);
            AscendC::Mutex::Unlock<PIPE_MTE3>(syncMutex);
            AscendC::Mutex::Lock<PIPE_MTE2>(syncMutex);
            AscendC::Mutex::Unlock<PIPE_MTE2>(syncMutex);
            AscendC::ReleaseMutexID(syncMutex);
        }
    }

    __aicore__ inline void UpdateAivBasicIndex()
    {
        uint64_t newBlockIdx = AscendC::GetBlockIdx() / (AscendC::GetTaskRatio() * kCnt_);
        aivParams_.kCntIndex = AscendC::GetBlockIdx() % (AscendC::GetTaskRatio() * kCnt_);

        aivParams_.indexParams = newBlockIdx;
        uint64_t cGmIndex = aivParams_.indexParams + (mCnt_ * nCnt_ - mCnt_ * nCnt_ % usedCoreNum_);
        uint64_t mainWindow = AscendC::Std::min(WINDOW_LEN, mCnt_);
        uint64_t mainRow = mCnt_ / mainWindow - 1UL;
        uint64_t tailWindow = mCnt_ - mainRow * mainWindow;
        uint64_t rowIdx = cGmIndex / nCnt_ / mainWindow;
        if (rowIdx < mainRow) {
            aivParams_.mCntIndex = rowIdx * mainWindow + cGmIndex % mainWindow;
            aivParams_.nCntIndex = (cGmIndex / mainWindow) % nCnt_;
        } else {
            rowIdx = mainRow;
            uint64_t tailIndex = cGmIndex - mainRow * mainWindow * nCnt_;
            aivParams_.mCntIndex = mainRow * mainWindow + tailIndex % tailWindow;
            aivParams_.nCntIndex = (tailIndex / tailWindow) % nCnt_;
        }
        // mod 2 means even row, need reverse scan
        if (rowIdx % NUM_TWO != 0UL) {
            aivParams_.nCntIndex = nCnt_ - 1UL - aivParams_.nCntIndex;
        }
    }

    __aicore__ inline void UpdateAivBasicBlock()
    {
        if (round_ < NUM_TWO) {
            aivParams_.curML1InAiv = aivParams_.mCntIndex != (mCnt_ - 1) ? mL1_ : (m_ - (mCnt_ - 1) * mL1_);
            aivParams_.curNL1InAiv = aivParams_.nCntIndex != (nCnt_ - 1) ? nL1_ : (n_ - (nCnt_ - 1) * nL1_);
            aivParams_.curAlignedNInAiv = aivParams_.curNL1InAiv;
        }
    }

    __aicore__ inline void UpdateAivParams(uint64_t index)
    {
        mBurstBase_ = CeilAlign(
            CeilDiv(aivParams_.curML1InAiv, kCnt_ * AscendC::GetTaskRatio()),
            CeilDiv(BLOCK_BYTE_SIZE, aivParams_.curAlignedNInAiv));
        uint64_t mBurstCnt = CeilDiv(aivParams_.curML1InAiv, mBurstBase_);
        uint64_t mBurstTail = aivParams_.curML1InAiv - (mBurstCnt - 1) * mBurstBase_;
        if (aivParams_.kCntIndex >= mBurstCnt) {
            copyGm2UbParams_.mBurstOri = 0;
        } else {
            copyGm2UbParams_.mBurstOri = (aivParams_.kCntIndex == mBurstCnt - 1) ? mBurstTail : mBurstBase_;
        }

        copyGm2UbParams_.kCnt = kCnt_;
        copyGm2UbParams_.mBurst = CeilDiv(copyGm2UbParams_.mBurstOri, aivMte2Num_);
        // Calculate init address of workspace for moving into UB.
        copyGm2UbParams_.offsetWorkspaceGM =
            (aivParams_.indexParams) * kCnt_ * BLOCK_BASE_M * BLOCK_BASE_N +
            (aivParams_.kCntIndex * mBurstBase_ + copyGm2UbParams_.mBurst * index) * aivParams_.curAlignedNInAiv;
        // Calculate init address of GM for moving out to GM.
        copyUb2GmParams_.offsetCGm = aivParams_.nCntIndex * nL1_ + aivParams_.mCntIndex * mL1_ * n_ +
                                     (aivParams_.kCntIndex * mBurstBase_ + copyGm2UbParams_.mBurst * index) * n_;
        uint64_t singleCnt = 1;
        if (index == singleCnt - 1) {
            copyGm2UbParams_.mBurst = copyGm2UbParams_.mBurstOri - (singleCnt - 1) * copyGm2UbParams_.mBurst;
        } else if (index >= singleCnt) {
            copyGm2UbParams_.mBurst = 0;
        }
        // datasize for moving in ub, align to 32B
        copyGm2UbParams_.burstLen =
            CeilAlign(copyGm2UbParams_.mBurst * aivParams_.curAlignedNInAiv, BASIC_BLOCK_SIZE_16);
        // gap of src between cur burst and next burst
        copyGm2UbParams_.srcGap = BLOCK_BASE_M * BLOCK_BASE_N - copyGm2UbParams_.burstLen;

        // args for ub2gm
        copyUb2GmParams_.mLength = copyGm2UbParams_.mBurst;
        copyUb2GmParams_.burstLen = aivParams_.curNL1InAiv;
        copyUb2GmParams_.dstGap = n_ - aivParams_.curNL1InAiv;
        copyUb2GmParams_.srcGap = aivParams_.curAlignedNInAiv - aivParams_.curNL1InAiv;
    }

    __aicore__ inline void operator()()
    {
        UpdateAivBasicIndex();
        UpdateAivBasicBlock();
        // ISASI: UB 单发边（MTE2<->V、V<->MTE3）用函数级局部 mutex 保守表达，operator() 末 Release。
        uint8_t ubMutex = AscendC::AllocMutexID();
        for (uint64_t index = 0; index < aivMte2Num_; ++index) {
            UpdateAivParams(index);
            LocalTensor<float> ubAddTensor{AscendC::TPosition::VECIN, 0, AscendC::TOTAL_UB_SIZE};
            DataCopyExtParams dataCopyExtParams{
                static_cast<uint16_t>(copyGm2UbParams_.kCnt),
                static_cast<uint32_t>(copyGm2UbParams_.burstLen * sizeof(float)),
                static_cast<uint32_t>(copyGm2UbParams_.srcGap * sizeof(float)), 0, 0};
            if (copyGm2UbParams_.mBurst == 0) {
                AscendC::ReleaseMutexID(ubMutex);
                return;
            }
            // MTE2->V：MTE2 侧包 DataCopyPad，V 侧包 Add。
            AscendC::Mutex::Lock<PIPE_MTE2>(ubMutex);
            DataCopyPad<float>(
                ubAddTensor, workspaceGlobal_[copyGm2UbParams_.offsetWorkspaceGM], dataCopyExtParams, {false, 0, 0, 0});
            AscendC::Mutex::Unlock<PIPE_MTE2>(ubMutex);

            AscendC::Mutex::Lock<PIPE_V>(ubMutex);
            for (uint64_t i = 1; i < copyGm2UbParams_.kCnt; ++i) {
                Add(ubAddTensor, ubAddTensor, ubAddTensor[i * copyGm2UbParams_.burstLen], copyGm2UbParams_.burstLen);
            }
            AscendC::Mutex::Unlock<PIPE_V>(ubMutex);

            DataCopyExtParams ub2gmExtParams{
                static_cast<uint16_t>(copyUb2GmParams_.mLength),
                static_cast<uint32_t>(copyUb2GmParams_.burstLen * sizeof(OutType)),
                static_cast<uint32_t>(copyUb2GmParams_.srcGap * sizeof(OutType) / BLOCK_BYTE_SIZE),
                static_cast<uint32_t>(copyUb2GmParams_.dstGap * sizeof(OutType)), 0};

            // V->MTE3：V 侧包 Cast，MTE3 侧包 DataCopyPad。
            if constexpr (AscendC::IsSameType<OutType, float>::value) {
                AscendC::Mutex::Lock<PIPE_MTE3>(ubMutex);
                DataCopyPad<OutType, PaddingMode::Compact>(
                    cGlobal_[copyUb2GmParams_.offsetCGm], ubAddTensor, ub2gmExtParams);
                AscendC::Mutex::Unlock<PIPE_MTE3>(ubMutex);
            } else {
                LocalTensor<OutType> ubCastDst{AscendC::TPosition::VECIN, 0, AscendC::TOTAL_UB_SIZE};
                AscendC::Mutex::Lock<PIPE_V>(ubMutex);
                Cast(ubCastDst, ubAddTensor, RoundMode::CAST_RINT, copyGm2UbParams_.burstLen);
                AscendC::Mutex::Unlock<PIPE_V>(ubMutex);
                AscendC::Mutex::Lock<PIPE_MTE3>(ubMutex);
                DataCopyPad<OutType, PaddingMode::Compact>(
                    cGlobal_[copyUb2GmParams_.offsetCGm], ubCastDst, ub2gmExtParams);
                AscendC::Mutex::Unlock<PIPE_MTE3>(ubMutex);
            }
        }
        AscendC::ReleaseMutexID(ubMutex);
    }
};
} // namespace Block
