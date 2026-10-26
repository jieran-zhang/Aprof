#ifndef APROF_DEVICE_SINGLE_ROLE_TASK_H
#define APROF_DEVICE_SINGLE_ROLE_TASK_H

// 统一 5/20 采集；算子提供完整调用、真实清 L2 kernel 和计时外输出快照。
#include "device_shared_timing.h"
#include "device_task_profile.h"
#include <cstring>
#include <chrono>

namespace aprof {

template<class Evict, class Launch, class Snapshot>
void RunSingleRoleTask(aclrtStream stream, const char *operator_name, const char *implementation,
                       size_t l2_bytes, size_t eviction_bytes, const SharedBuffers &buffers,
                       Evict evict, Launch launch, Snapshot snapshot) {
    using namespace shared_detail;
    const char *capture_id = std::getenv("APROF_TASK_CAPTURE_ID");
    const char *case_id = std::getenv("APROF_TASK_CASE_ID");
    if (!stream || !operator_name || !*operator_name || !implementation || !*implementation ||
        !capture_id || !*capture_id || !case_id || !*case_id ||
        std::string(case_id).find_first_not_of("0123456789") != std::string::npos ||
        std::stoll(case_id) <= 0 || !std::getenv("APROF_TASK_PROFILE_DIR") ||
        !l2_bytes || eviction_bytes <= l2_bytes)
        throw std::invalid_argument("invalid single-role Task identity or L2 eviction size");
    ValidateBuffers(buffers);
    Identity identity;
    int32_t physical_before = 0, physical_after = 0;
    Check(aclrtGetPhyDevIdByLogicDevId(identity.device, &physical_before), "physical identity");
    const auto cost_start = std::chrono::steady_clock::now();
    Check(aclrtSynchronizeStream(stream), "single-role initial synchronize");
    std::vector<std::vector<unsigned char>> original_inputs;
    for (const auto &span : buffers.inputs) {
        original_inputs.emplace_back(span.bytes);
        Check(aclrtMemcpy(original_inputs.back().data(), span.bytes, span.data, span.bytes,
                          ACL_MEMCPY_DEVICE_TO_HOST), "single-role input snapshot");
    }
    const auto warmup_start = std::chrono::steady_clock::now();
    for (int i = 0; i < 5; ++i) {
        launch(stream, buffers);
        Check(aclrtSynchronizeStream(stream), "single-role warmup synchronize");
    }
    const auto warmup_end = std::chrono::steady_clock::now();
    TaskProfile profile;
    profile.Start(static_cast<uint32_t>(identity.device));
    const auto formal_start = std::chrono::steady_clock::now();
    for (int i = 0; i < 20; ++i) {
        evict(stream);
        launch(stream, buffers);
        Check(aclrtSynchronizeStream(stream), "single-role formal synchronize");
    }
    const auto formal_end = std::chrono::steady_clock::now();
    profile.Finish();
    const auto profile_end = std::chrono::steady_clock::now();
    identity.Verify();
    Check(aclrtGetPhyDevIdByLogicDevId(identity.device, &physical_after), "physical identity recheck");
    if (physical_before != physical_after) throw std::runtime_error("physical device changed");
    snapshot(implementation, stream, buffers);
    for (size_t i = 0; i < buffers.inputs.size(); ++i) {
        const auto &span = buffers.inputs[i];
        std::vector<unsigned char> after(span.bytes);
        Check(aclrtMemcpy(after.data(), span.bytes, span.data, span.bytes,
                          ACL_MEMCPY_DEVICE_TO_HOST), "single-role input recheck");
        if (after != original_inputs[i])
            throw std::runtime_error("single-role input changed during capture");
    }
    const auto output_end = std::chrono::steady_clock::now();
    auto seconds = [](auto a, auto b) { return std::chrono::duration<double>(b-a).count(); };
    std::cout << "APROF_NATIVE_COST_JSON:{\"input_snapshot_seconds\":" << seconds(cost_start, warmup_start)
              << ",\"warmup_seconds\":" << seconds(warmup_start, warmup_end)
              << ",\"profiler_start_seconds\":" << seconds(warmup_end, formal_start)
              << ",\"formal_host_seconds\":" << seconds(formal_start, formal_end)
              << ",\"profiler_finish_seconds\":" << seconds(formal_end, profile_end)
              << ",\"output_and_identity_seconds\":" << seconds(profile_end, output_end) << "}" << std::endl;
    std::cout << "APROF_SINGLE_ROLE_TASK_JSON:{\"protocol\":\"single_role_l2_clean_task_v1\""
              << ",\"operator\":" << Quote(operator_name) << ",\"implementation\":" << Quote(implementation)
              << ",\"case_id\":" << std::stoll(case_id) << ",\"capture_id\":" << Quote(capture_id)
              << ",\"pid\":" << identity.pid << ",\"device\":" << identity.device
              << ",\"physical_id\":" << physical_before
              << ",\"warmup_calls\":5,\"formal_calls\":20,\"l2_bytes\":" << l2_bytes
              << ",\"eviction_bytes\":" << eviction_bytes << ",\"input_bytes_unchanged\":true}" << std::endl;
    if (!std::cout) throw std::runtime_error("single-role Task journal write failed");
}

} // namespace aprof

#endif
