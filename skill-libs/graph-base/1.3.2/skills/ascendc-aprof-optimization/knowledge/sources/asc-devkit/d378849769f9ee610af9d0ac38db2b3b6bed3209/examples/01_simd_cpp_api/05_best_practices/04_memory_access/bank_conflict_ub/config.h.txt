/**
 * Copyright (c) 2026 Huawei Technologies Co., Ltd.
 * This program is free software, you can redistribute it and/or modify it under the terms and conditions of
 * CANN Open Software License Agreement Version 2.0 (the "License").
 * Please refer to the License for details. You may not use this file except in compliance with the License.
 * THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
 * INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
 * See LICENSE in the root of the software repository for the full text of the License.
 */

/* !
 * \file config.h
 * \brief Config for src and dst address.
 */

#ifndef BANK_CONFLICT_UB_CONFIG_H
#define BANK_CONFLICT_UB_CONFIG_H

#include "kernel_operator.h"

constexpr uint32_t TOTAL_LENGTH = 4096;

#if SCENARIO_NUM == 1
constexpr uint32_t xLocalAddr = 0x0000;
constexpr uint32_t yLocalAddr = 0x10100;
constexpr uint32_t zLocalAddr = 0x20000;

#elif SCENARIO_NUM == 2

constexpr uint32_t xLocalAddr = 0x0000;
constexpr uint32_t yLocalAddr = 0x4000;
constexpr uint32_t zLocalAddr = 0x10000;

#elif SCENARIO_NUM == 3

constexpr uint32_t xLocalAddr = 0x0000;
constexpr uint32_t yLocalAddr = 0x10000;
constexpr uint32_t zLocalAddr = 0x14100;

#elif SCENARIO_NUM == 4

constexpr uint32_t xLocalAddr = 0x0000;
constexpr uint32_t yLocalAddr = 0x10100;
constexpr uint32_t zLocalAddr = 0x4000;

#elif SCENARIO_NUM == 5

constexpr uint32_t xLocalAddr = 0x0000;
constexpr uint32_t yLocalAddr = 0x10100;
constexpr uint32_t zLocalAddr = 0x4020;

#elif SCENARIO_NUM == 6

constexpr uint32_t xLocalAddr = 0x0000;
constexpr uint32_t yLocalAddr = 0x10100;
constexpr uint32_t zLocalAddr = 0x10100;

#elif SCENARIO_NUM == 7

constexpr uint32_t xLocalAddr = 0x0000;
constexpr uint32_t yLocalAddr = 0x10100;
constexpr uint32_t zLocalAddr = 0x10100;

#elif SCENARIO_NUM == 8

constexpr uint32_t xLocalAddr = 0x0000;
constexpr uint32_t yLocalAddr = 0x10100;
constexpr uint32_t zLocalAddr = 0x10100;

#endif

#endif // BANK_CONFLICT_UB_CONFIG_H
