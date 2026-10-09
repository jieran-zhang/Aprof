#ifndef APROF_CANNBENCH_DEVICE_TIMER_H
#define APROF_CANNBENCH_DEVICE_TIMER_H
// Host-only timing support. Input preparation and copies precede Run().
#include <cmath>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <utility>
#include "acl/acl.h"
namespace aprof {
inline void Check(aclError e, const char *what) {
    if (e != ACL_SUCCESS) throw std::runtime_error(std::string("aprof ") + what + ": " + std::to_string(e));
}
inline int Setting(const char *key, int fallback, int minimum=1) {
    const char *raw = std::getenv(key);
    if (!raw) return fallback;
    size_t used = 0;
    int value = std::stoi(raw, &used);
    if (used != std::string(raw).size() || value < minimum || value > 1000000)
        throw std::invalid_argument(std::string("invalid ") + key);
    return value;
}
inline bool Enabled() { return std::getenv("APROF_TIMING") || std::getenv("APROF_TIMING_INTERACTIVE"); }
struct Buffer {
    void *pointer = nullptr;
    explicit Buffer(size_t bytes) { Check(aclrtMalloc(&pointer, bytes, ACL_MEM_MALLOC_HUGE_FIRST), "allocate prepared buffer"); }
    ~Buffer() { if (pointer) aclrtFree(pointer); }
    Buffer(const Buffer&) = delete;
    Buffer& operator=(const Buffer&) = delete;
    uint8_t *at(size_t offset=0) { return static_cast<uint8_t *>(pointer) + offset; }
};
struct Event {
    aclrtEvent event = nullptr;
    Event() { Check(aclrtCreateEventWithFlag(&event, ACL_EVENT_TIME_LINE), "create timing event"); }
    ~Event() { if (event) aclrtDestroyEvent(event); }
};
struct CapturedOperator {
    aclrtStream stream;
    aclmdlRI model = nullptr;
    bool capturing = false;
    bool submitted = false;
    explicit CapturedOperator(aclrtStream value) : stream(value) {}
    CapturedOperator(const CapturedOperator&) = delete;
    CapturedOperator& operator=(const CapturedOperator&) = delete;
    ~CapturedOperator() {
        // CaptureEnd also unwinds a capture interrupted by a throwing launch.
        // Preserve the original exception if cleanup itself cannot succeed.
        if (capturing) {
            aclmdlRI abandoned = nullptr;
            aclmdlRICaptureEnd(stream, &abandoned);
            if (abandoned && abandoned != model) aclmdlRIDestroy(abandoned);
        }
        // A replay may have been queued before a later event operation failed.
        if (submitted) aclrtSynchronizeStream(stream);
        if (model) aclmdlRIDestroy(model);
    }
    template<class Launch> void Capture(int repeat, Launch& launch) {
        Check(aclmdlRICaptureBegin(stream, ACL_MODEL_RI_CAPTURE_MODE_GLOBAL), "capture begin");
        capturing = true;
        for (int i=0; i<repeat; ++i) launch();
        Check(aclmdlRICaptureEnd(stream, &model), "capture end");
        capturing = false;
        if (!model) throw std::runtime_error("aprof capture returned a null model");
    }
    void Replay() {
        submitted = true;
        Check(aclmdlRIExecuteAsync(model, stream), "captured operator replay");
    }
};
template<class Launch> void Run(aclrtStream stream, int device, const char *op, size_t launches, Launch launch) {
    if (!Enabled()) { launch(); return; }
    const int warmup = Setting("APROF_WARMUP", 10, 0);
    const int repeat = Setting("APROF_REPEAT", 100);
    const int capture_replay = Setting("APROF_CAPTURE_REPLAY", 0, 0);
    if (capture_replay > 1) throw std::invalid_argument("invalid APROF_CAPTURE_REPLAY");
    for (int i=0; i<warmup; ++i) launch();
    Check(aclrtSynchronizeStream(stream), "warmup synchronize");
    Event start, end;
    // Declared after the events so pending replay is drained before their
    // destruction. Capture/allocation are outside all measured event intervals.
    CapturedOperator captured(stream);
    if (capture_replay) captured.Capture(repeat, launch);
    int index = 0;
    auto sample = [&]() {
        Check(aclrtRecordEvent(start.event, stream), "record start");
        if (capture_replay) captured.Replay();
        else for (int i=0; i<repeat; ++i) launch();
        Check(aclrtRecordEvent(end.event, stream), "record end");
        Check(aclrtSynchronizeEvent(end.event), "sample synchronize");
        captured.submitted = false;
        float milliseconds = 0;
        Check(aclrtEventElapsedTime(&milliseconds, start.event, end.event), "elapsed time");
        const double ns = static_cast<double>(milliseconds) * 1000000.0 / repeat;
        if (!std::isfinite(ns) || ns <= 0) throw std::runtime_error("nonpositive or nonfinite device duration");
        std::cout << "APROF_TIMING_JSON:{\"schema_version\":\"1.0.0\",\"operator\":\"" << op
                  << "\",\"device\":" << device << ",\"source\":\"acl_event\",\"unit\":\"ns\",\"sample_index\":" << index++
                  << ",\"warmup\":" << warmup << ",\"repeat\":" << repeat << ",\"launches_per_operator\":" << launches
                  ;
        if (capture_replay)
            std::cout << ",\"execution_mode\":\"acl_graph_replay\",\"captured_operator_calls\":" << repeat;
        std::cout << ",\"elapsed_ns\":" << std::setprecision(17) << ns << "}" << std::endl;
    };
    if (std::getenv("APROF_TIMING_INTERACTIVE")) {
        std::cout << "APROF_TIMING_READY" << std::endl;
        std::string command;
        while (std::getline(std::cin, command)) {
            if (command == "quit") break;
            if (command != "sample") throw std::invalid_argument("unknown timing protocol command");
            sample();
        }
    } else {
        const int samples = Setting("APROF_SAMPLES", 1);
        for (int i=0; i<samples; ++i) sample();
    }
}
}
#endif
