cmake_minimum_required(VERSION 3.16)

find_package(ASC REQUIRED)

project(reduce_sum LANGUAGES ASC CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT DEFINED ENV{ASCEND_HOME_PATH})
    message(FATAL_ERROR "ASCEND_HOME_PATH is not set. Please source scripts/setup_env.sh first.")
endif()

set(ASCEND_PATH "$ENV{ASCEND_HOME_PATH}")
set(ACL_INCLUDE_DIR "${ASCEND_PATH}/x86_64-linux/include")
set(ACL_LIB_DIR "${ASCEND_PATH}/lib64")

if(NOT EXISTS "${ACL_INCLUDE_DIR}")
    set(ACL_INCLUDE_DIR "${ASCEND_PATH}/include")
endif()

add_executable(reduce_sum op_host/reduce_sum.asc)

target_include_directories(reduce_sum PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/op_kernel
    ${CMAKE_CURRENT_SOURCE_DIR}/op_host
    ${ACL_INCLUDE_DIR}
)

target_link_directories(reduce_sum PRIVATE
    ${ACL_LIB_DIR}
    "${ASCEND_PATH}/x86_64-linux/lib64"
)

target_link_libraries(reduce_sum PRIVATE
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

target_compile_options(reduce_sum PRIVATE
    $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=dav-3510>
)

install(TARGETS reduce_sum RUNTIME DESTINATION ${CMAKE_CURRENT_BINARY_DIR})
