// Copyright (c) 2026 AProf contributors.
// This program is free software, you can redistribute it and/or modify it under the terms and conditions of
// CANN Open Software License Agreement Version 2.0 (the "License").
// Please refer to the License for details. You may not use this file except in compliance with the License.
// THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
// INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
// See LICENSE in the root of the software repository for the full text of the License.

#include <acl/acl.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <vector>

// Appended to the generated kernel with APROF_CASE_* constants.
int main(int argc, char** argv)
{
    int device = 0;
    if (argc > 1) {
        char* end = nullptr;
        long parsed = std::strtol(argv[1], &end, 10);
        if (*end || parsed < 0 || parsed > 65535) {
            return 1;
        }
        device = static_cast<int>(parsed);
    }
    if (aclInit(nullptr) != ACL_SUCCESS || aclrtSetDevice(device) != ACL_SUCCESS) {
        return 2;
    }
    aclrtStream stream;
    if (aclrtCreateStream(&stream) != ACL_SUCCESS) {
        return 3;
    }
    std::vector<float> input(APROF_CASE_SIZE), output(APROF_CASE_OUTPUT);
    std::vector<int32_t> indices(APROF_CASE_OUTPUT);
    for (int i = 0; i < APROF_CASE_SIZE; ++i) {
        input[i] = static_cast<float>((i * 17) % 19 - 9);
    }
    void *x = nullptr, *y = nullptr, *ix = nullptr;
    size_t inputBytes = input.size() * sizeof(float);
    size_t outputBytes = output.size() * sizeof(float);
    if (aclrtMalloc(&x, inputBytes, ACL_MEM_MALLOC_HUGE_FIRST) != ACL_SUCCESS ||
        aclrtMalloc(&y, outputBytes, ACL_MEM_MALLOC_HUGE_FIRST) != ACL_SUCCESS ||
        aclrtMalloc(&ix, indices.size() * sizeof(int32_t), ACL_MEM_MALLOC_HUGE_FIRST) != ACL_SUCCESS) {
        return 4;
    }
    if (aclrtMemcpy(x, inputBytes, input.data(), inputBytes, ACL_MEMCPY_HOST_TO_DEVICE) != ACL_SUCCESS) {
        return 5;
    }
    aprof_case<<<1, nullptr, stream>>>((GM_ADDR)x, (GM_ADDR)y, (GM_ADDR)ix);
    if (aclrtSynchronizeStream(stream) != ACL_SUCCESS ||
        aclrtMemcpy(output.data(), outputBytes, y, outputBytes, ACL_MEMCPY_DEVICE_TO_HOST) != ACL_SUCCESS) {
        return 6;
    }
    if (APROF_CASE_TOPK && aclrtMemcpy(
                               indices.data(), indices.size() * sizeof(int32_t), ix, indices.size() * sizeof(int32_t),
                               ACL_MEMCPY_DEVICE_TO_HOST) != ACL_SUCCESS) {
        return 7;
    }
    bool correct = true;
    double maxError = 0;
    if (APROF_CASE_TOPK) {
        std::vector<int32_t> order(input.size());
        for (int i = 0; i < APROF_CASE_SIZE; ++i) {
            order[i] = i;
        }
        std::stable_sort(order.begin(), order.end(), [&](int a, int b) { return input[a] > input[b]; });
        for (int i = 0; i < APROF_CASE_OUTPUT; ++i) {
            correct = correct && output[i] == input[order[i]] && indices[i] == order[i];
        }
    } else {
        double maximum = *std::max_element(input.begin(), input.end()), total = 0;
        for (float value : input) {
            total += std::exp(static_cast<double>(value) - maximum);
        }
        for (int i = 0; i < APROF_CASE_OUTPUT; ++i) {
            double expected = std::exp(static_cast<double>(input[i]) - maximum) / total;
            double error = std::abs(output[i] - expected);
            correct = correct && std::isfinite(output[i]) && error <= 1e-5;
            maxError = std::max(maxError, error);
        }
    }
    std::printf(
        "CORRECTNESS %s size=%d outputs=%d max_error=%.9g\n", correct ? "passed" : "failed", APROF_CASE_SIZE,
        APROF_CASE_OUTPUT, maxError);
    aclrtFree(x);
    aclrtFree(y);
    aclrtFree(ix);
    aclrtDestroyStream(stream);
    aclrtResetDevice(device);
    aclFinalize();
    return correct ? 0 : 8;
}
