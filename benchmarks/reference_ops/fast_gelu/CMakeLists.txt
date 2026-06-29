cmake_minimum_required(VERSION 3.16)

find_package(ASC REQUIRED)

project(fast_gelu LANGUAGES ASC CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_ASC_ARCHITECTURES "dav-3510" CACHE STRING "NPU architecture: dav-2201 (910B), dav-3510 (950)")

if(NOT DEFINED ENV{ASCEND_HOME_PATH})
    message(FATAL_ERROR "ASCEND_HOME_PATH is not set. Please source scripts/setup_env.sh first.")
endif()

set(ASCEND_PATH "$ENV{ASCEND_HOME_PATH}")
set(ACL_INCLUDE_DIR "${ASCEND_PATH}/x86_64-linux/include")
set(ACL_LIB_DIR "${ASCEND_PATH}/lib64")

if(NOT EXISTS "${ACL_INCLUDE_DIR}")
    set(ACL_INCLUDE_DIR "${ASCEND_PATH}/include")
endif()

add_executable(fast_gelu op_host/fast_gelu.asc)

target_include_directories(fast_gelu PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/op_kernel
    ${CMAKE_CURRENT_SOURCE_DIR}/op_host
    ${ACL_INCLUDE_DIR}
)

target_link_directories(fast_gelu PRIVATE
    ${ACL_LIB_DIR}
    "${ASCEND_PATH}/x86_64-linux/lib64"
)

target_link_libraries(fast_gelu PRIVATE
    ascendcl
    tiling_api
    register
    platform
    unified_dlog
    dl
    m
    pthread
    graph_base
)

target_compile_options(fast_gelu PRIVATE
    $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=${CMAKE_ASC_ARCHITECTURES}>
)

install(TARGETS fast_gelu RUNTIME DESTINATION ${CMAKE_CURRENT_BINARY_DIR})
