/**
 * Copyright (c) 2025 Huawei Technologies Co., Ltd.
 * This program is free software, you can redistribute it and/or modify it under the terms and conditions of
 * CANN Open Software License Agreement Version 2.0 (the "License").
 * Please refer to the License for details. You may not use this file except in compliance with the License.
 * THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
 * INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
 * See LICENSE in the root of the software repository for the full text of the License.
 */

/*!
 * \file squared_relu.h
 * \brief squared_relu head file
 */
#ifndef SQUARED_RELU_H
#define SQUARED_RELU_H

#include <type_traits>
#include "kernel_operator.h"
#include "lib/matmul_intf.h"

namespace SquaredRelu {

using namespace AscendC;

constexpr int32_t MAX_UB_SIZE = 192 * 1024;
constexpr int32_t PP_ELEMENT_NUM = 24 * 1024;
constexpr int32_t ONE_REPEAT_ELE_NUM_FP32 = 64;

template <typename T>
class SquaredReluND {
public:
    TPipe pipe;
    __aicore__ inline SquaredReluND(){};
    __aicore__ inline void Init(GM_ADDR input, GM_ADDR output, GM_ADDR workspace,
                                const SquaredReluTilingData* tilingData);
    __aicore__ inline void Process();

private:
    __aicore__ inline void CopyInAndCast(int64_t inputOffset, int64_t dataCount);
    __aicore__ inline void Compute(int64_t dataCount);
    __aicore__ inline void CastAndCopyOut(int64_t outputOffset, int64_t dataCount);

private:
    TBuf<QuePosition::VECCALC> ubTBuf;
    LocalTensor<uint8_t> tmpTensor;

    LocalTensor<uint8_t> selMaskOne;
    LocalTensor<uint8_t> selMaskTwo;

    LocalTensor<T> xTmp;

    LocalTensor<T> xTensor;

    LocalTensor<float> xTensorFp32;

    GlobalTensor<T> inputGm;
    GlobalTensor<T> outputGm;

    int64_t elementNum;
    uint32_t needCoreNumber;
    int32_t blockIdx;

    event_t eventId = EVENT_ID0;
    int32_t pingPongFlag = 0;
};

template <typename T>
__aicore__ inline void SquaredReluND<T>::Init(GM_ADDR input, GM_ADDR output, GM_ADDR workspace,
                                              const SquaredReluTilingData* tilingData)
{
    inputGm.SetGlobalBuffer((__gm__ T*)input);
    outputGm.SetGlobalBuffer((__gm__ T*)output);

    elementNum = tilingData->elementNum;
    needCoreNumber = tilingData->needCoreNum;

    blockIdx = GetBlockIdx();
    pipe.InitBuffer(ubTBuf, MAX_UB_SIZE);
    tmpTensor = ubTBuf.Get<uint8_t>();
}

template <typename T>
__aicore__ inline void SquaredReluND<T>::Process()
{
    if (blockIdx >= needCoreNumber) {
        return;
    }

    int64_t totalTimes = elementNum / PP_ELEMENT_NUM;
    int64_t remain = elementNum % PP_ELEMENT_NUM;
    if (remain > 0) {
        totalTimes++;
    }
    int64_t loopNum = totalTimes / needCoreNumber;
    int64_t loopRemain = totalTimes % needCoreNumber;

    if (loopRemain > 0 && blockIdx < loopRemain) {
        loopNum++;
    }
    int64_t eachCoreStartOffset = loopNum * blockIdx * PP_ELEMENT_NUM;
    if (loopRemain > 0) {
        if (blockIdx >= loopRemain) {
            eachCoreStartOffset += elementNum % (PP_ELEMENT_NUM * needCoreNumber);
        }
    }

    int32_t calNum = PP_ELEMENT_NUM;
    int64_t lastCoreNum = loopRemain == 0 ? needCoreNumber - 1 : loopRemain - 1;
    pingPongFlag = 0;
    SetFlag<HardEvent::MTE3_MTE2>(EVENT_ID0);
    SetFlag<HardEvent::MTE3_MTE2>(EVENT_ID1);
    for (int64_t i = 0; i < loopNum; i++) {
        int64_t localOffset = i * PP_ELEMENT_NUM;

        // 最后一轮的最后一个核处理余数
        if (remain > 0 && i == loopNum - 1 && blockIdx == lastCoreNum) {
            calNum = remain;
        }
        eventId = pingPongFlag ? EVENT_ID1 : EVENT_ID0;
        CopyInAndCast(eachCoreStartOffset + localOffset, calNum);

        Compute(calNum);
        CastAndCopyOut(eachCoreStartOffset + localOffset, calNum);
        pingPongFlag = 1 - pingPongFlag;
    }
    WaitFlag<HardEvent::MTE3_MTE2>(EVENT_ID0);
    WaitFlag<HardEvent::MTE3_MTE2>(EVENT_ID1);
}

template <typename T>
__aicore__ inline void SquaredReluND<T>::CopyInAndCast(int64_t inputOffset, int64_t dataCount)
{
    xTensor = pingPongFlag ? tmpTensor[MAX_UB_SIZE / 2].ReinterpretCast<T>() : tmpTensor[0].ReinterpretCast<T>();
    WaitFlag<HardEvent::MTE3_MTE2>(eventId);

    DataCopyExtParams dataCopyParams{1, static_cast<uint32_t>(dataCount * sizeof(T)), 0, 0, 0};
    DataCopyPadExtParams<T> padParams{false, 0, 0, 0};
    if (std::is_same_v<T, bfloat16_t> || std::is_same_v<T, half>) {
        int32_t elementByte = PP_ELEMENT_NUM * sizeof(T);
        xTmp = pingPongFlag ? tmpTensor[elementByte + MAX_UB_SIZE / 2].ReinterpretCast<T>() :
                              tmpTensor[elementByte].ReinterpretCast<T>();
        DataCopyPad(xTmp, inputGm[inputOffset], dataCopyParams, padParams);
    } else {
        DataCopyPad(xTensor, inputGm[inputOffset], dataCopyParams, padParams);
    }

    SetFlag<HardEvent::MTE2_V>(eventId);
    WaitFlag<HardEvent::MTE2_V>(eventId);

    xTensorFp32 = xTensor.template ReinterpretCast<float>();
    if (std::is_same_v<T, bfloat16_t> || std::is_same_v<T, half>) {
        Cast(xTensorFp32, xTmp, RoundMode::CAST_NONE, dataCount);
        PipeBarrier<PIPE_V>();
    }
}

template <typename T>
__aicore__ inline void SquaredReluND<T>::Compute(int64_t dataCount)
{
    Relu(xTensorFp32, xTensorFp32, dataCount);
    PipeBarrier<PIPE_V>();
    Mul(xTensorFp32, xTensorFp32, xTensorFp32, dataCount);
    PipeBarrier<PIPE_V>();
}

template <typename T>
__aicore__ inline void SquaredReluND<T>::CastAndCopyOut(int64_t outputOffset, int64_t dataCount)
{
    if (std::is_same_v<T, half>) {
        Cast(xTensor, xTensorFp32, RoundMode::CAST_NONE, dataCount);
        PipeBarrier<PIPE_V>();
    } else if (std::is_same_v<T, bfloat16_t>) {
        Cast(xTensor, xTensorFp32, RoundMode::CAST_RINT, dataCount);
        PipeBarrier<PIPE_V>();
    }
    SetFlag<HardEvent::V_MTE3>(eventId);
    WaitFlag<HardEvent::V_MTE3>(eventId);
    DataCopyExtParams dataCopyParams{1, static_cast<uint32_t>(dataCount * sizeof(T)), 0, 0, 0};
    DataCopyPad(outputGm[outputOffset], xTensor, dataCopyParams);
    SetFlag<HardEvent::MTE3_MTE2>(eventId);
}

} // namespace SquaredRelu
#endif