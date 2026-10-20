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
 * \file matmul_kernel_streamk.h
 * \brief Kernel-side StreamK  implementation.
 */

#pragma once

#if ASC_DEVKIT_MAJOR >= 9
#include "kernel_basic_intf.h"
#else
#include "kernel_operator.h"
#include "kernel_operator_intf.h"
#endif

#include "kernel_utils/common_utils.h"
#include "include/tensor_api/tensor.h"

#include "../block/matmul_block_mmad_streamk.h"
#include "../block/matmul_block_scheduler_streamk.h"
#include "../utils/constant.h"

namespace Kernel {

template <class ProblemShape, class BlockMmad, class BlockScheduler, class BlockEpilogue>
class MatmulKernelStreamK {
public:
    __aicore__ inline MatmulKernelStreamK()
    {}
    __aicore__ inline ~MatmulKernelStreamK()
    {}

    static constexpr bool transA = BlockMmad::transA;
    static constexpr bool transB = BlockMmad::transB;

    using BlockSchedulerOp =
        typename Block::BlockSchedulerSelector<ProblemShape, BlockScheduler, transA, transB>::SchedulerOp;

    using BlockMmadParams = typename BlockMmad::Params;
    using TypeA = typename BlockMmad::TypeA;
    using TypeB = typename BlockMmad::TypeB;
    using TypeC = typename BlockMmad::TypeC;

    using TupleShape = AscendC::Shape<int64_t, int64_t, int64_t>;
    using BlockShape = AscendC::Shape<int64_t, int64_t, int64_t, int64_t>;
    using TupleL1L0Shape = AscendC::Shape<int64_t, int64_t, int64_t, int64_t, int64_t, int64_t>;
    using BlockCoord = AscendC::Coord<int64_t, int64_t, int64_t, int64_t>;
    using BlockSchedulerParams = typename BlockSchedulerOp::Params;
    using BlockEpilogueParams = typename BlockEpilogue::Params;

    using MakeLayoutA = typename BlockMmad::LayoutA;
    using MakeLayoutB = typename BlockMmad::LayoutB;
    using MakeLayoutC = typename BlockMmad::LayoutC;

    __gm__ float* workspaceGmAddr_;

    struct KernelParams {
        uint32_t mL1;
        uint32_t nL1;
        uint32_t kL1;
        uint32_t baseM;
        uint32_t baseN;
        uint32_t baseK;
        uint32_t usedCoreNum;
        bool isHf32;
    };

    struct Params {
        ProblemShape problemShape;
        BlockMmadParams mmadParams;
        BlockSchedulerParams schParams;
        BlockEpilogueParams epilogueParams;
        KernelParams kernelParams;
    };

public:
    __aicore__ inline void operator()(const Params& params);

    __aicore__ inline void UnsetHf32(bool isHf32) {
        if (isHf32) {
            AscendC::SetHF32Mode(0);
        }
    }

private:
    __aicore__ inline TupleShape ToShapeTuple(const ProblemShape& problemShape)
    {
        return {problemShape.m, problemShape.n, problemShape.k};
    }

private:
    int64_t usedCoreNum_{0};
    TupleShape problemShape_{};
    BlockMmadParams blockMmadParams_{};
};

template <class ProblemShape, class BlockMmad, class BlockScheduler, class BlockEpilogue>
__aicore__ inline void MatmulKernelStreamK<ProblemShape, BlockMmad, BlockScheduler, BlockEpilogue>::operator()(
    const Params& params)
{
    usedCoreNum_ = params.kernelParams.usedCoreNum;
    if (usedCoreNum_ <= 0) {
        return;
    }
    problemShape_ = ToShapeTuple(params.problemShape);
    blockMmadParams_ = params.mmadParams;
    workspaceGmAddr_ = reinterpret_cast<__gm__ float*>(blockMmadParams_.workspaceGmAddr);
    BlockSchedulerOp bs(params.problemShape, params.schParams);
    TupleShape tileL1 = {params.kernelParams.mL1, params.kernelParams.nL1, params.kernelParams.kL1};
    int64_t mL1 = asc::te::get<MNK_M>(tileL1);
    int64_t nL1 = asc::te::get<MNK_N>(tileL1);
    int64_t kL1 = asc::te::get<MNK_K>(tileL1);
    int64_t mTileNum = asc::te::get<MNK_M>(bs.GetMNKTileNum());
    int64_t nTileNum = asc::te::get<MNK_N>(bs.GetMNKTileNum());
    int64_t skKTileNum = asc::te::get<MNK_K>(bs.GetMNKTileNum()); // it only used in sk
    int64_t tileNum = bs.GetTotalTileNum();

    if ASCEND_IS_AIC {
        int64_t curBlockIdx = block_idx;
        TupleShape tileL0 = {params.kernelParams.baseM, params.kernelParams.baseN, params.kernelParams.baseK};
        if (curBlockIdx >= bs.GetBlockNum(usedCoreNum_)) {
            AscendC::CrossCoreSetFlag<AIC_SYNC_AIV_MODE_4, PIPE_FIX>(AIC_SYNC_AIV_FLAG);
            AscendC::CrossCoreSetFlag<AIC_SYNC_AIV_MODE_4, PIPE_FIX>(AIC_SYNC_AIV_FLAG + FLAG_ID_MAX);
            return;
        }
        // enbale Hf32
        if (params.kernelParams.isHf32) {
            AscendC::SetHF32Mode(1);
            AscendC::SetHF32TransMode(1);
        }
        AscendC::SetMMLayoutTransform(true);
        BlockMmad blockMmadOp(problemShape_, tileL1, tileL0);
        int64_t tailSKTotalTileNum = static_cast<int64_t>(((mTileNum * nTileNum) % usedCoreNum_) * skKTileNum);
        int64_t m = asc::te::get<MNK_M>(problemShape_);
        int64_t n = asc::te::get<MNK_N>(problemShape_);
        int64_t k = asc::te::get<MNK_K>(problemShape_);

        auto layoutA = MakeLayoutA{}(m, k);
        auto layoutB = MakeLayoutB{}(k, n);
        auto layoutC = MakeLayoutC{}(m, n);

        auto gmA = asc::te::make_tensor(
            asc::te::make_mem_ptr<asc::te::location::gm>(
                reinterpret_cast<__gm__ TypeA*>(blockMmadParams_.aGmAddr)),
            layoutA);
        auto gmB = asc::te::make_tensor(
            asc::te::make_mem_ptr<asc::te::location::gm>(
                reinterpret_cast<__gm__ TypeB*>(blockMmadParams_.bGmAddr)),
            layoutB);
        auto gmC = asc::te::make_tensor(
            asc::te::make_mem_ptr<asc::te::location::gm>(
                reinterpret_cast<__gm__ TypeC*>(blockMmadParams_.cGmAddr)),
            layoutC);

        for (int64_t tileIdx = curBlockIdx; tileIdx < tileNum; tileIdx += usedCoreNum_) {
            int64_t tmpTileIdx = tileIdx;
            if (!bs.CheckIsSkScene(0)) { // SK Preload in DP+SK
                if (tileIdx % usedCoreNum_ < tailSKTotalTileNum &&
                    (CeilDiv(tileIdx + 1, usedCoreNum_) == (CeilDiv(tileNum, usedCoreNum_) - 1))) {
                    tmpTileIdx = tileIdx + usedCoreNum_;
                } else if (
                    tileIdx % usedCoreNum_ < tailSKTotalTileNum &&
                    (CeilDiv(tileIdx + 1, usedCoreNum_) == CeilDiv(tileNum, usedCoreNum_))) {
                    tmpTileIdx = tileIdx - usedCoreNum_;
                }
            }
            auto singleCoreShape = bs.GetSingleCoreShape(tmpTileIdx);
            auto singleCoreCoord = bs.GetSingleCoreCoord(tmpTileIdx);
            int64_t kSingleCore = bs.GetCurKSingleCore(tmpTileIdx);
            int64_t offsetWorkspace =
                (((tmpTileIdx % usedCoreNum_) / skKTileNum) * skKTileNum + asc::te::get<MNK_K>(singleCoreCoord)) * BLOCK_BASE_M *
                BLOCK_BASE_N;
            auto layoutWorkspace = asc::te::make_frame_layout<asc::te::nd_ext_layout_ptn>(
                asc::te::get<MNK_M>(singleCoreShape), asc::te::get<MNK_N>(singleCoreShape));
            auto gmWorkSpace =
                asc::te::make_tensor(asc::te::make_mem_ptr<asc::te::location::gm>(workspaceGmAddr_ + offsetWorkspace), layoutWorkspace);
            auto gmBlockA = gmA.slice(asc::te::make_coord(asc::te::get<MNK_M>(singleCoreCoord) * mL1, asc::te::get<MNK_K>(singleCoreCoord) * kSingleCore),
                asc::te::make_shape(asc::te::get<MNK_M>(singleCoreShape), asc::te::get<MNK_K>(singleCoreShape)));
            auto gmBlockB = gmB.slice(asc::te::make_coord(asc::te::get<MNK_K>(singleCoreCoord) * kSingleCore, asc::te::get<MNK_N>(singleCoreCoord) * nL1),
                asc::te::make_shape(asc::te::get<MNK_K>(singleCoreShape), asc::te::get<MNK_N>(singleCoreShape)));
            auto gmBlockC =
                gmC.slice(asc::te::make_coord(asc::te::get<MNK_M>(singleCoreCoord) * mL1, asc::te::get<MNK_N>(singleCoreCoord) * nL1),
                    asc::te::make_shape(asc::te::get<MNK_M>(singleCoreShape), asc::te::get<MNK_N>(singleCoreShape)));
            blockMmadOp(
                gmBlockC, gmBlockA, gmBlockB, gmWorkSpace, singleCoreShape, asc::te::get<MNK_K>(singleCoreCoord),
                bs.CheckIsSkScene(tmpTileIdx));
            if (tmpTileIdx + usedCoreNum_ >= tileNum) {
                AscendC::CrossCoreSetFlag<AIC_SYNC_AIV_MODE_4, PIPE_FIX>(AIC_SYNC_AIV_FLAG);
                AscendC::CrossCoreSetFlag<AIC_SYNC_AIV_MODE_4, PIPE_FIX>(AIC_SYNC_AIV_FLAG + FLAG_ID_MAX);
            }
        }
        AscendC::SetMMLayoutTransform(false);
        UnsetHf32(params.kernelParams.isHf32);
    }
    if ASCEND_IS_AIV {
        uint64_t lastLoopTotalCnt = (mTileNum * nTileNum % usedCoreNum_) * skKTileNum;
        uint64_t curBlockIdxInAiv = AscendC::GetBlockIdx();
        if (curBlockIdxInAiv >= lastLoopTotalCnt * AscendC::GetTaskRatio()) {
            AscendC::CrossCoreWaitFlag<AIC_SYNC_AIV_MODE_4, PIPE_MTE3>(AIC_SYNC_AIV_FLAG);
            AscendC::SyncAll();
            return;
        }

        AscendC::CrossCoreWaitFlag<AIC_SYNC_AIV_MODE_4, PIPE_MTE3>(AIC_SYNC_AIV_FLAG);
        AscendC::SyncAll();
        BlockEpilogue epilogueOp;
        epilogueOp.Init(
            params.epilogueParams, problemShape_, tileL1, bs.GetMNKTileNum(), usedCoreNum_, bs.CheckIsSkScene(0));
        epilogueOp();
    }
}

} // namespace Kernel
