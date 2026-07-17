cmake_minimum_required(VERSION 3.16)

find_package(ASC REQUIRED)

project(swi_glu_baseline LANGUAGES ASC CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_ASC_ARCHITECTURES "dav-2201" CACHE STRING "NPU architecture")

if(NOT DEFINED ENV{ASCEND_HOME_PATH})
    message(FATAL_ERROR "ASCEND_HOME_PATH is not set")
endif()

set(ASCEND_PATH "$ENV{ASCEND_HOME_PATH}")
set(ACL_INCLUDE_DIR "${ASCEND_PATH}/x86_64-linux/include")
if(NOT EXISTS "${ACL_INCLUDE_DIR}")
    set(ACL_INCLUDE_DIR "${ASCEND_PATH}/include")
endif()

add_executable(swi_glu_baseline op_host/main.asc)
target_include_directories(swi_glu_baseline PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/op_kernel
    ${CMAKE_CURRENT_SOURCE_DIR}/op_host
    ${ACL_INCLUDE_DIR}
)
target_link_directories(swi_glu_baseline PRIVATE
    ${ASCEND_PATH}/lib64
    ${ASCEND_PATH}/x86_64-linux/lib64
    ${ASCEND_PATH}/aarch64-linux/lib64
)
target_link_libraries(swi_glu_baseline PRIVATE ascendcl tiling_api register platform unified_dlog dl m pthread graph_base)
target_compile_options(swi_glu_baseline PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=${CMAKE_ASC_ARCHITECTURES}>)
