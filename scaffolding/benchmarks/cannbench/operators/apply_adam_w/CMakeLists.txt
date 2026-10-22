# ----------------------------------------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
# ----------------------------------------------------------------------------------------------------------

# ============================================================================
# CMake 构建配置 - Ascend C Kernel 直调
# ============================================================================
#
# 目录结构:
#   op_kernel/     - NPU 计算层（tiling.h + kernel.asc）
#   op_host/       - Host 直调层（.asc 入口 + data_utils.h）
#   op_extension/  - PyTorch 接入层（torch.cpp + register.cpp + ops.h）
#   scripts/       - 测试脚本
#
# [MODIFY] 创建新算子时修改:
# 1. 所有 apply_adam_w → <your_op>（apply_adam_w 是整体算子名，_kernel/_host/_ops 是固定后缀）
# 2. target_compile_options 中的 --npu-arch
# ============================================================================

cmake_minimum_required(VERSION 3.16)

find_package(ASC REQUIRED)

# [MODIFY] 工程名
project(apply_adam_w LANGUAGES ASC CXX)

set(CMAKE_CXX_STANDARD 17)

set(ACL_INCLUDE_DIR "$ENV{ASCEND_HOME_PATH}/aarch64-linux/include")
set(ACL_LIB_DIR "$ENV{ASCEND_HOME_PATH}/lib64")

# ============================================================================
# Target 1: 可执行文件（直调验证）
# ============================================================================

# [MODIFY] 目标名和源文件名
add_executable(apply_adam_w op_host/apply_adam_w.asc)

target_link_libraries(apply_adam_w PRIVATE
    tiling_api
    register
    platform
    unified_dlog
    dl
    m
    graph_base
)

target_include_directories(apply_adam_w PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/op_kernel
    ${CMAKE_CURRENT_SOURCE_DIR}/op_host
)

# [CONFIG] NPU 架构配置
# - dav-2201: Atlas A2 系列（默认）
# - dav-3510: Atlas A5 系列
# 更多架构详见 npu-arch skill
# [MODIFY] 工程名 - apply_adam_w → <your_op>
target_compile_options(apply_adam_w PRIVATE
    $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=dav-2201>
)

# ============================================================================
# Target 2: TORCH_LIBRARY 模块 (libapply_adam_w_ops.so)
#   Python: torch.ops.load_library("build/libapply_adam_w_ops.so")
#           torch.ops.npu.apply_adam_w(x1, x2)
# ============================================================================

option(BUILD_TORCH_EXTENSION "Build the optional PyTorch NPU extension" OFF)

if(BUILD_TORCH_EXTENSION)
find_package(Python3 COMPONENTS Interpreter Development REQUIRED)

execute_process(
    COMMAND ${Python3_EXECUTABLE} -c "import torch; print(torch.utils.cmake_prefix_path)"
    OUTPUT_STRIP_TRAILING_WHITESPACE
    OUTPUT_VARIABLE TORCH_CMAKE_PREFIX_PATH
)
list(APPEND CMAKE_PREFIX_PATH ${TORCH_CMAKE_PREFIX_PATH})
find_package(Torch REQUIRED)

execute_process(
    COMMAND ${Python3_EXECUTABLE} -c "import os, torch_npu; print(os.path.dirname(torch_npu.__file__))"
    OUTPUT_STRIP_TRAILING_WHITESPACE
    OUTPUT_VARIABLE TORCH_NPU_PATH
)
set(TORCH_NPU_INCLUDE_DIRS ${TORCH_NPU_PATH}/include)
set(TORCH_NPU_LIBRARIES ${TORCH_NPU_PATH}/lib)

# [MODIFY] 所有 apply_adam_w → <your_op>（保持 _ops 后缀）
add_library(apply_adam_w_ops SHARED
    op_kernel/apply_adam_w_kernel.asc
    op_extension/apply_adam_w_torch.cpp
    op_extension/register.cpp
)

target_include_directories(apply_adam_w_ops PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/op_kernel
    ${CMAKE_CURRENT_SOURCE_DIR}/op_host
    ${CMAKE_CURRENT_SOURCE_DIR}/op_extension
    ${TORCH_INCLUDE_DIRS}
    ${TORCH_NPU_INCLUDE_DIRS}
    ${Python3_INCLUDE_DIRS}
    ${ACL_INCLUDE_DIR}
)

target_link_libraries(apply_adam_w_ops PRIVATE
    torch_npu
    tiling_api
    register
    platform
    unified_dlog
    dl
    m
    graph_base
    ascendcl
    ascendc_runtime
)

target_link_directories(apply_adam_w_ops PRIVATE
    ${ACL_LIB_DIR}
    "$ENV{ASCEND_HOME_PATH}/aarch64-linux/lib64"
    ${TORCH_NPU_LIBRARIES}
)

target_compile_options(apply_adam_w_ops PRIVATE
    ${TORCH_CXX_FLAGS}
    $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=dav-2201>
)

message(STATUS "TORCH_LIBRARY module 'libapply_adam_w_ops.so' will be built")
else()
message(STATUS "PyTorch extension disabled; configure with -DBUILD_TORCH_EXTENSION=ON when TorchConfig.cmake is available")
endif()
