#pragma once
#include "device_shared_timing.h"

namespace aprof {
// Exploration only. The formal header and its command protocol stay unchanged.
template<class A, class B, class S>
void RunTaskScreen(aclrtStream stream, const char *op, const SharedBuffers &buffers,
                   A baseline, B candidate, S snapshot) {
    using namespace shared_detail;
    if (!stream || (std::string(op) != "exp" && std::string(op) != "sigmoid")
            || !std::getenv("APROF_TASK_PROFILE_DIR")
            || std::getenv("APROF_SHARED_MODE") || std::getenv("APROF_SHARED_REPEAT")
            || std::getenv("APROF_SHARED_COMMANDS") || std::getenv("APROF_SHARED_CYCLE"))
        throw std::invalid_argument("screen requires its own Task capture environment");
    ValidateBuffers(buffers);
    Identity identity;
    Check(aclrtSynchronizeStream(stream), "screen initial sync");
    std::vector<std::vector<unsigned char>> original;
    for (const auto &span : buffers.inputs) {
        original.emplace_back(span.bytes);
        Check(aclrtMemcpy(original.back().data(), span.bytes, span.data, span.bytes,
                          ACL_MEMCPY_DEVICE_TO_HOST), "screen input snapshot");
    }
    const char *roles[] = {"baseline", "candidate"};
    auto launch = [&](int role) {
        if (role == 0) baseline(stream, buffers); else candidate(stream, buffers);
    };
    auto interval = [&](int role, int calls, bool save) {
        const uint64_t began = Now();
        for (int i = 0; i < calls; ++i) launch(role);
        Check(aclrtSynchronizeStream(stream), "screen complete calls");
        if (save) snapshot(roles[role], stream, buffers);
        const uint64_t ended = Now();
        identity.Verify();
        std::ostringstream out;
        out << "{\"implementation\":" << Quote(roles[role])
            << ",\"launches_per_operator\":1,\"started_monotonic_ns\":" << began
            << ",\"finished_monotonic_ns\":" << ended << '}';
        return out.str();
    };
    auto emit = [&](const char *kind, uint64_t began, uint64_t ended, const std::string &fields) {
        identity.Verify();
        std::ostringstream out;
        out << "APROF_TASK_SCREEN_JSON:{\"schema_version\":\"1.0.0\",\"protocol\":\"shared_buffer_msprof_task_screen_v1\""
            << ",\"operator\":" << Quote(op) << ",\"kind\":" << Quote(kind)
            << ",\"pid\":" << identity.pid << ",\"device\":" << identity.device
            << ",\"context_address\":" << Address(identity.context) << ",\"stream_address\":" << Address(stream)
            << ",\"warmup\":10,\"repeat\":100,\"prime_repeat\":100,\"pairs\":6"
            << ",\"launches_per_operator\":{\"baseline\":1,\"candidate\":1}"
            << ",\"role_symbols\":{\"baseline\":\"launch_baseline\",\"candidate\":\"launch_candidate\"}"
            << ",\"buffers\":{\"inputs\":";
        Spans(out, buffers.inputs); out << ",\"outputs\":"; Spans(out, buffers.outputs);
        out << ",\"workspaces\":"; Spans(out, buffers.workspaces);
        out << "},\"started_monotonic_ns\":" << began << ",\"finished_monotonic_ns\":" << ended << fields << '}';
        std::cout << out.str() << std::endl;
        if (!std::cout) throw std::runtime_error("screen protocol output failed");
    };
    uint64_t began = Now();
    for (int role : {0, 1}) for (int i = 0; i < 10; ++i) launch(role);
    Check(aclrtSynchronizeStream(stream), "screen warmup sync");
    emit("ready", began, Now(), "");
    began = Now();
    for (int role : {0, 1, 1, 0}) for (int i = 0; i < 100; ++i) launch(role);
    Check(aclrtSynchronizeStream(stream), "screen prime sync");
    emit("prime", began, Now(), ",\"order\":[\"baseline\",\"candidate\",\"candidate\",\"baseline\"]");
    for (int pair = 0; pair < 6; ++pair) {
        began = Now();
        const int first = pair % 2;
        std::string samples[2];
        samples[first] = interval(first, 100, false);
        samples[1-first] = interval(1-first, 100, false);
        emit("pair", began, Now(), ",\"pair_index\":" + std::to_string(pair)
             + ",\"order\":[" + Quote(roles[first]) + "," + Quote(roles[1-first]) + "]"
             + ",\"baseline\":" + samples[0] + ",\"candidate\":" + samples[1]);
    }
    began = Now();
    const std::string a = interval(0, 1, true), b = interval(1, 1, true);
    for (size_t i = 0; i < buffers.inputs.size(); ++i) {
        const auto &span = buffers.inputs[i];
        std::vector<unsigned char> after(span.bytes);
        Check(aclrtMemcpy(after.data(), span.bytes, span.data, span.bytes,
                          ACL_MEMCPY_DEVICE_TO_HOST), "screen input recheck");
        if (after != original[i]) throw std::runtime_error("screen callback modified input bytes");
    }
    emit("complete", began, Now(), ",\"untimed_verifications\":[" + a + "," + b + "]"
         + ",\"input_bytes_unchanged\":true");
}
} // namespace aprof
