cmake_minimum_required(VERSION 3.16)
find_package(ASC REQUIRED)
project(foreach_addcdiv_scalar_direct LANGUAGES ASC CXX)
set(CMAKE_CXX_STANDARD 17)

add_executable(foreach_addcdiv_scalar op_host/foreach_addcdiv_scalar.asc)
target_include_directories(foreach_addcdiv_scalar PRIVATE op_host op_kernel)
target_link_libraries(foreach_addcdiv_scalar PRIVATE
    tiling_api register platform unified_dlog dl m graph_base ascendcl ascendc_runtime)
target_link_directories(foreach_addcdiv_scalar PRIVATE
    "$ENV{ASCEND_HOME_PATH}/lib64" "$ENV{ASCEND_HOME_PATH}/aarch64-linux/lib64")
target_compile_options(foreach_addcdiv_scalar PRIVATE
    $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=dav-2201>)
