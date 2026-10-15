#ifndef APROF_DEVICE_TIMING_DIAGNOSTIC_H
#define APROF_DEVICE_TIMING_DIAGNOSTIC_H
// Research-only worker: unchanged kernel, explicit physical buffer slots.
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include <sched.h>
#include <time.h>
#include <unistd.h>
#include "acl/acl.h"

namespace aprof_diag {
inline void Check(aclError code, const char *label) {
    if (code != ACL_SUCCESS) throw std::runtime_error(std::string(label) + ": " + std::to_string(code));
}
inline int Setting(const char *name, int fallback) {
    const char *value = std::getenv(name);
    if (!value) return fallback;
    size_t used = 0; int result = std::stoi(value, &used);
    if (used != std::string(value).size() || result < 1 || result > 1000000)
        throw std::invalid_argument(std::string("invalid ") + name);
    return result;
}
inline uint64_t Now(clockid_t clock = CLOCK_MONOTONIC) {
    timespec value{};
    if (clock_gettime(clock, &value)) throw std::runtime_error("clock_gettime");
    return uint64_t(value.tv_sec) * 1000000000ULL + value.tv_nsec;
}
inline std::string Pointer(void *value) {
    std::ostringstream text; text << value; return text.str();
}
struct Allocation {
    void *value = nullptr;
    explicit Allocation(size_t bytes) { Check(aclrtMalloc(&value, bytes, ACL_MEM_MALLOC_HUGE_FIRST), "diagnostic allocation"); }
    ~Allocation() { if (value) aclrtFree(value); }
    Allocation(const Allocation&) = delete;
};
struct Event {
    aclrtEvent value = nullptr;
    Event() { Check(aclrtCreateEventWithFlag(&value, ACL_EVENT_TIME_LINE), "create event"); }
    ~Event() { if (value) aclrtDestroyEvent(value); }
};
inline void Common(const char *type, const char *op, int device, aclrtContext context, aclrtStream stream) {
    std::cout << "APROF_DIAG_JSON:{\"type\":\"" << type << "\",\"operator\":\"" << op
        << "\",\"pid\":" << getpid() << ",\"device\":" << device
        << ",\"context\":\"" << Pointer(context) << "\",\"stream\":\"" << Pointer(stream)
        << "\",\"monotonic_ns\":" << Now() << ",\"unix_ns\":" << Now(CLOCK_REALTIME)
        << ",\"cpu\":" << sched_getcpu();
}

template<class Launch> void Run(aclrtStream stream, int device, const char *op,
        void *input0, void *output0, void *tiling0, size_t bytes, size_t tiling_bytes, Launch launch) {
    const int slots = Setting("APROF_DIAG_SLOTS", 1), repeat = Setting("APROF_DIAG_REPEAT", 100);
    if (slots != 1 && slots != 2) throw std::invalid_argument("diagnostic slots must be 1 or 2");
    aclrtContext context = nullptr;
    Check(aclrtGetCurrentContext(&context), "current context");
    if (!context) throw std::runtime_error("missing diagnostic context");
    // Slots are independently allocated; role crossover never reallocates them.
    std::vector<void *> inputs{input0}, outputs{output0}, tilings{tiling0};
    std::vector<Allocation *> owned;
    struct Cleanup { std::vector<Allocation *>& values; ~Cleanup() { for (auto *v : values) delete v; } } cleanup{owned};
    if (slots == 2) {
        for (size_t size : {bytes, bytes, tiling_bytes}) owned.push_back(new Allocation(size));
        inputs.push_back(owned[0]->value); outputs.push_back(owned[1]->value); tilings.push_back(owned[2]->value);
        Check(aclrtMemcpy(inputs[1], bytes, inputs[0], bytes, ACL_MEMCPY_DEVICE_TO_DEVICE), "duplicate input");
        Check(aclrtMemcpy(tilings[1], tiling_bytes, tilings[0], tiling_bytes, ACL_MEMCPY_DEVICE_TO_DEVICE), "duplicate tiling");
    }
    for (int slot = 0; slot < slots; ++slot)
        for (int i = 0; i < 10; ++i) launch(inputs[slot], outputs[slot], tilings[slot]);
    Check(aclrtSynchronizeStream(stream), "warmup synchronize");
    Event start, end;
    Common("ready", op, device, context, stream);
    std::cout << ",\"warmup\":10,\"repeat\":" << repeat << ",\"allocation_policy\":\"ACL_MEM_MALLOC_HUGE_FIRST\",\"buffers\":[";
    for (int slot = 0; slot < slots; ++slot) {
        if (slot) std::cout << ',';
        std::cout << "{\"slot\":" << slot << ",\"input\":\"" << Pointer(inputs[slot])
            << "\",\"output\":\"" << Pointer(outputs[slot]) << "\",\"tiling\":\"" << Pointer(tilings[slot])
            << "\",\"bytes\":" << bytes << ",\"tiling_bytes\":" << tiling_bytes << '}';
    }
    std::cout << "],\"affinity\":[";
    cpu_set_t cpus; CPU_ZERO(&cpus);
    if (sched_getaffinity(0, sizeof(cpus), &cpus)) throw std::runtime_error("sched_getaffinity");
    bool comma = false;
    for (int cpu = 0; cpu < CPU_SETSIZE; ++cpu) if (CPU_ISSET(cpu, &cpus)) {
        if (comma) std::cout << ','; std::cout << cpu; comma = true;
    }
    std::cout << "]}" << std::endl;
    std::ifstream commands;
    if (const char *path = std::getenv("APROF_DIAG_COMMANDS")) {
        commands.open(path); if (!commands) throw std::runtime_error("open commands");
    }
    std::istream& control = commands.is_open() ? static_cast<std::istream&>(commands) : std::cin;
    std::string line; uint64_t expected_sequence = 0;
    while (std::getline(control, line)) {
        if (line == "quit") break;
        std::istringstream fields(line); std::string verb, extra; int slot = -1; uint64_t sequence = 0;
        if (!(fields >> verb >> slot >> sequence) || (fields >> extra) || slot < 0 || slot >= slots
                || sequence != expected_sequence++ || (verb != "prime" && verb != "sample"))
            throw std::invalid_argument("diagnostic command identity mismatch");
        int cpu_before = sched_getcpu(); uint64_t begin = Now();
        if (verb == "prime") {
            for (int i = 0; i < 100; ++i) launch(inputs[slot], outputs[slot], tilings[slot]);
            Check(aclrtSynchronizeStream(stream), "prime synchronize");
            Common("prime", op, device, context, stream);
            std::cout << ",\"sequence\":" << sequence << ",\"slot\":" << slot
                << ",\"repeat\":100,\"started_monotonic_ns\":" << begin << "}" << std::endl;
            continue;
        }
        Check(aclrtRecordEvent(start.value, stream), "record start");
        uint64_t enqueue_begin = Now();
        for (int i = 0; i < repeat; ++i) launch(inputs[slot], outputs[slot], tilings[slot]);
        Check(aclrtRecordEvent(end.value, stream), "record end");
        uint64_t enqueue_end = Now();
        Check(aclrtSynchronizeEvent(end.value), "synchronize end");
        uint64_t synchronized = Now(); float milliseconds = 0;
        Check(aclrtEventElapsedTime(&milliseconds, start.value, end.value), "event elapsed");
        double ns = double(milliseconds) * 1000000.0 / repeat;
        if (!std::isfinite(ns) || ns <= 0) throw std::runtime_error("invalid duration");
        Common("sample", op, device, context, stream);
        std::cout << ",\"sequence\":" << sequence << ",\"slot\":" << slot << ",\"repeat\":" << repeat
            << ",\"event_ns_per_operator\":" << std::setprecision(17) << ns
            << ",\"started_monotonic_ns\":" << begin << ",\"enqueue_begin_monotonic_ns\":" << enqueue_begin
            << ",\"enqueue_end_monotonic_ns\":" << enqueue_end << ",\"synchronized_monotonic_ns\":" << synchronized
            << ",\"cpu_before\":" << cpu_before << ",\"cpu_after\":" << sched_getcpu() << "}" << std::endl;
    }
    if (slots == 2) {
        const char *path = std::getenv("APROF_DIAG_OUTPUT1");
        if (!path) throw std::invalid_argument("second output path required");
        std::vector<char> output(bytes);
        Check(aclrtMemcpy(output.data(), bytes, outputs[1], bytes, ACL_MEMCPY_DEVICE_TO_HOST), "diagnostic D2H slot1");
        std::ofstream file(path, std::ios::binary); file.write(output.data(), bytes);
        if (!file) throw std::runtime_error("write second output");
    }
    Common("completed", op, device, context, stream); std::cout << "}" << std::endl;
}
}
#endif
