#ifndef APROF_DEVICE_SHARED_TIMING_H
#define APROF_DEVICE_SHARED_TIMING_H
// Qualification is external and binds the exact header and collector bytes.
// Both callbacks launch their COMPLETE operation on the supplied stream and
// buffers. Inputs are read-only; outputs must be fully defined on every call;
// scratch initialization belongs to each complete call. In-place/stateful
// operations and callbacks that change context/stream are unsupported.
// Final byte equality detects persistent input changes, not temporary writes.
#include <acl/acl.h>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sched.h>
#include <sstream>
#include <stdexcept>
#include <string>
#include <time.h>
#include <unistd.h>
#include <vector>

namespace aprof {
struct SharedBufferSpan {
    std::string name;
    void *data;
    size_t bytes;
};
struct SharedBuffers {
    std::vector<SharedBufferSpan> inputs, outputs, workspaces;
};

namespace shared_detail {
constexpr int kWarmup = 10, kPrime = 100, kPairs = 5;
constexpr const char *kProtocol = "shared_buffer_acl_event_v2";
inline void Check(aclError value, const char *operation) {
    if (value != ACL_SUCCESS)
        throw std::runtime_error(std::string("aprof shared ") + operation + ": " + std::to_string(value));
}
inline uint64_t Now() {
    struct timespec value {};
    if (clock_gettime(CLOCK_MONOTONIC, &value) != 0)
        throw std::runtime_error("aprof shared monotonic clock failed");
    return static_cast<uint64_t>(value.tv_sec) * 1000000000ULL + static_cast<uint64_t>(value.tv_nsec);
}
inline int Cpu() {
    const int value = sched_getcpu();
    if (value < 0) throw std::runtime_error("shared timing CPU query failed");
    return value;
}
inline std::string Affinity() {
    cpu_set_t mask;
    CPU_ZERO(&mask);
    if (sched_getaffinity(0, sizeof(mask), &mask) != 0)
        throw std::runtime_error("shared timing affinity query failed");
    std::ostringstream out;
    out << '[';
    bool first = true;
    for (int cpu = 0; cpu < CPU_SETSIZE; ++cpu) if (CPU_ISSET(cpu, &mask)) {
        if (!first) out << ',';
        first = false;
        out << cpu;
    }
    out << ']';
    return out.str();
}
inline std::string Quote(const std::string &value) {
    std::ostringstream out;
    out << '"';
    for (unsigned char c : value) {
        if (c == '"' || c == '\\') out << '\\' << static_cast<char>(c);
        else if (c < 0x20) out << "\\u" << std::hex << std::setw(4) << std::setfill('0') << static_cast<unsigned>(c) << std::dec;
        else out << static_cast<char>(c);
    }
    out << '"';
    return out.str();
}
inline std::string Address(const void *value) {
    return Quote(std::to_string(reinterpret_cast<uintptr_t>(value)));
}
inline void Spans(std::ostream &out, const std::vector<SharedBufferSpan> &spans) {
    out << '[';
    bool first = true;
    for (const auto &span : spans) {
        if (!first) out << ',';
        first = false;
        out << "{\"name\":" << Quote(span.name) << ",\"address\":" << Address(span.data)
            << ",\"bytes\":" << span.bytes << '}';
    }
    out << ']';
}
inline void ValidateBuffers(const SharedBuffers &buffers) {
    if (buffers.inputs.empty() || buffers.outputs.empty())
        throw std::invalid_argument("shared timing requires input and output spans");
    std::vector<const SharedBufferSpan *> all;
    for (const auto *group : {&buffers.inputs, &buffers.outputs, &buffers.workspaces})
        for (const auto &span : *group) {
            const uintptr_t begin = reinterpret_cast<uintptr_t>(span.data);
            if (span.name.empty() || !span.data || !span.bytes || span.bytes > std::numeric_limits<uintptr_t>::max() - begin)
                throw std::invalid_argument("invalid shared timing buffer span");
            for (const auto *prior : all) {
                const uintptr_t previous = reinterpret_cast<uintptr_t>(prior->data);
                if (span.name == prior->name || (begin < previous + prior->bytes && previous < begin + span.bytes))
                    throw std::invalid_argument("shared spans must have unique names and must not overlap");
            }
            all.push_back(&span);
        }
}
struct Event {
    aclrtStream stream;
    aclrtEvent value = nullptr;
    explicit Event(aclrtStream s) : stream(s) {
        Check(aclrtCreateEventWithFlag(&value, ACL_EVENT_TIME_LINE), "create event");
    }
    ~Event() {
        // Drain queued work on exceptional paths before destroying an event.
        aclrtSynchronizeStream(stream);
        if (value) aclrtDestroyEvent(value);
    }
    Event(const Event &) = delete;
    Event &operator=(const Event &) = delete;
};
struct Identity {
    aclrtContext context = nullptr;
    int32_t device = -1;
    pid_t pid = getpid();
    Identity() {
        Check(aclrtGetCurrentContext(&context), "get context");
        Check(aclrtGetDevice(&device), "get device");
        if (!context) throw std::runtime_error("shared timing requires a current ACL context");
    }
    void Verify() const {
        aclrtContext current = nullptr;
        int32_t actual_device = -1;
        Check(aclrtGetCurrentContext(&current), "recheck context");
        Check(aclrtGetDevice(&actual_device), "recheck device");
        if (current != context || actual_device != device || getpid() != pid)
            throw std::runtime_error("shared timing context/device/process changed");
    }
};
struct Sample {
    const char *implementation;
    size_t launches;
    float milliseconds;
    double nanoseconds;
    uint64_t started, finished;
    int cpu_before, cpu_after;
};
inline void WriteSample(std::ostream &out, const Sample &sample) {
    out << "{\"implementation\":" << Quote(sample.implementation)
        << ",\"launches_per_operator\":" << sample.launches
        << ",\"elapsed_ms\":" << std::setprecision(17) << static_cast<double>(sample.milliseconds)
        << ",\"elapsed_ns\":" << sample.nanoseconds
        << ",\"started_monotonic_ns\":" << sample.started
        << ",\"finished_monotonic_ns\":" << sample.finished
        << ",\"cpu_before\":" << sample.cpu_before << ",\"cpu_after\":" << sample.cpu_after << '}';
}
inline void NoExtra(std::istringstream &line) {
    std::string extra;
    if (line >> extra) throw std::invalid_argument("extra shared timing command tokens");
}
} // namespace shared_detail

// Launch callbacks: callback(aclrtStream, const SharedBuffers&).
// Snapshot: snapshot(const char *role, aclrtStream, const SharedBuffers&).
// Snapshot saves each role separately; the independent oracle runs after exit.
// role_symbols names the host callbacks. An A/A confirmation may deliberately
// register two distinct callbacks that invoke the same original kernel.
template<class BaselineLaunch, class CandidateLaunch, class Snapshot>
void RunShared(aclrtStream stream, const char *operator_name, int cycle_index,
               size_t baseline_launches, size_t candidate_launches,
               const SharedBuffers &buffers, const std::array<const char *, 2> &role_symbols,
               BaselineLaunch baseline, CandidateLaunch candidate, Snapshot snapshot) {
    using namespace shared_detail;
    if (!stream || !operator_name || !*operator_name || cycle_index < 0 || cycle_index >= 6
            || !baseline_launches || !candidate_launches
            || !role_symbols[0] || !*role_symbols[0] || !role_symbols[1] || !*role_symbols[1])
        throw std::invalid_argument("invalid shared timing identity or complete-call launch counts");
    // A baseline-only pilot fixes a case repeat before fresh confirmation processes.
    // All samples measure sustained complete calls, not isolated-call latency.
    const char *mode_text = std::getenv("APROF_SHARED_MODE");
    const char *repeat_text = std::getenv("APROF_SHARED_REPEAT");
    if (!mode_text || !repeat_text) throw std::invalid_argument("shared mode/repeat required");
    const std::string mode(mode_text), repeat_string(repeat_text);
    if ((mode != "pilot" && mode != "confirmation") || repeat_string.empty()
            || repeat_string.find_first_not_of("0123456789") != std::string::npos)
        throw std::invalid_argument("invalid shared mode/repeat");
    const unsigned long parsed_repeat = std::stoul(repeat_string);
    if (parsed_repeat < 100 || parsed_repeat > 100000 || parsed_repeat % 100
            || (mode == "pilot" && (parsed_repeat != 100 || cycle_index != 0)))
        throw std::invalid_argument("shared repeat/cycle outside frozen bounds");
    const int kRepeat = static_cast<int>(parsed_repeat);
    std::ifstream command_file;
    std::istream *commands = &std::cin;
    if (const char *path = std::getenv("APROF_SHARED_COMMANDS")) {
        if (!*path) throw std::invalid_argument("empty shared timing command file path");
        command_file.open(path);
        if (!command_file.is_open()) throw std::runtime_error("cannot open shared timing command file");
        commands = &command_file;
    }
    ValidateBuffers(buffers);
    Identity identity;
    Event start(stream), end(stream);
    Check(aclrtSynchronizeStream(stream), "initial synchronize");
    std::vector<std::vector<unsigned char>> original_inputs;
    for (const auto &span : buffers.inputs) {
        original_inputs.emplace_back(span.bytes);
        Check(aclrtMemcpy(original_inputs.back().data(), span.bytes, span.data, span.bytes,
                          ACL_MEMCPY_DEVICE_TO_HOST), "snapshot immutable input");
    }
    auto launch = [&](const char *role, const std::string &phase) {
        if (phase == "formal" && std::string(role) == "candidate") candidate(stream, buffers);
        else baseline(stream, buffers);
    };
    auto emit = [&](const char *kind, const std::string &fields) {
        identity.Verify();
        std::ostringstream out;
        out << "APROF_SHARED_TIMING_JSON:{\"schema_version\":\"1.0.0\",\"protocol\":" << Quote(kProtocol)
            << ",\"kind\":" << Quote(kind) << ",\"operator\":" << Quote(operator_name)
            << ",\"cycle_index\":" << cycle_index << ",\"pid\":" << identity.pid
            << ",\"device\":" << identity.device << ",\"context_address\":" << Address(identity.context)
            << ",\"stream_address\":" << Address(stream)
            << ",\"warmup\":10,\"repeat\":" << kRepeat << ",\"prime_repeat\":100,\"execution_mode\":\"direct_enqueue\",\"mode\":" << Quote(mode)
            << ",\"warmup_role_counts\":{\"baseline\":" << (mode == "pilot" ? 20 : 10)
            << ",\"candidate\":" << (mode == "pilot" ? 0 : 10) << '}'
            << ",\"launches_per_operator\":{\"baseline\":" << baseline_launches << ",\"candidate\":" << candidate_launches << '}'
            << ",\"role_symbols\":{\"baseline\":" << Quote(role_symbols[0]) << ",\"candidate\":" << Quote(role_symbols[1]) << '}'
            << ",\"buffers\":{\"inputs\":";
        Spans(out, buffers.inputs);
        out << ",\"outputs\":"; Spans(out, buffers.outputs);
        out << ",\"workspaces\":"; Spans(out, buffers.workspaces);
        out << '}' << fields << '}';
        // Emit only after both role intervals; no I/O between them.
        std::cout << out.str() << std::endl;
        if (!std::cout) throw std::runtime_error("shared timing protocol output failed");
    };
    const char *roles[] = {"baseline", "candidate"};
    const uint64_t warmup_started = Now();
    if (mode == "pilot") {
        for (int i = 0; i < 2 * kWarmup; ++i) baseline(stream, buffers);
    } else {
        for (int slot = 0; slot < 2; ++slot) {
            const char *role = roles[(slot + cycle_index) % 2];
            for (int i = 0; i < kWarmup; ++i) launch(role, "formal");
        }
    }
    Check(aclrtSynchronizeStream(stream), "warmup synchronize");
    const uint64_t warmup_finished = Now();
    emit("ready", ",\"warmup_started_monotonic_ns\":" + std::to_string(warmup_started)
        + ",\"warmup_finished_monotonic_ns\":" + std::to_string(warmup_finished)
        + ",\"cpu_affinity\":" + Affinity());
    auto measure = [&](auto &callback, const char *implementation, size_t launches) {
        Sample sample;
        sample.implementation = implementation;
        sample.launches = launches;
        sample.cpu_before = Cpu();
        sample.started = Now();
        Check(aclrtRecordEvent(start.value, stream), "record start");
        // Select the callback BEFORE the start event. The measured loop does
        // no phase/role string dispatch and no per-launch synchronization.
        for (int i = 0; i < kRepeat; ++i) callback(stream, buffers);
        Check(aclrtRecordEvent(end.value, stream), "record end");
        Check(aclrtSynchronizeEvent(end.value), "sample synchronize");
        Check(aclrtEventElapsedTime(&sample.milliseconds, start.value, end.value), "event elapsed time");
        sample.nanoseconds = static_cast<double>(sample.milliseconds) * 1000000.0 / kRepeat;
        sample.finished = Now();
        sample.cpu_after = Cpu();
        if (!std::isfinite(sample.nanoseconds) || sample.nanoseconds <= 0)
            throw std::runtime_error("nonpositive or nonfinite shared timing sample");
        identity.Verify();
        return sample;
    };

    if (mode == "pilot") {
        auto expect = [&](const std::string &expected) {
            std::string received;
            if (!std::getline(*commands, received) || received != expected)
                throw std::invalid_argument("shared pilot command differs");
        };
        expect("prime 0 pilot");
        const uint64_t began = Now();
        for (int i = 0; i < 4 * kPrime; ++i) baseline(stream, buffers);
        Check(aclrtSynchronizeStream(stream), "pilot prime synchronize");
        emit("prime", ",\"command_index\":0,\"phase\":\"pilot\",\"prime_order\":[\"baseline\",\"baseline\",\"baseline\",\"baseline\"],\"started_monotonic_ns\":"
            + std::to_string(began) + ",\"finished_monotonic_ns\":" + std::to_string(Now()));
        for (int i = 0; i < 3; ++i) {
            expect("sample " + std::to_string(i + 1) + " pilot " + std::to_string(i));
            const Sample sample = measure(baseline, "baseline", baseline_launches);
            std::ostringstream fields;
            fields << ",\"command_index\":" << i + 1 << ",\"sample_index\":" << i
                << ",\"phase\":\"pilot\",\"baseline\":";
            WriteSample(fields, sample);
            emit("pilot_sample", fields.str());
        }
        expect("finish 4");
            std::ostringstream fields;
            fields << ",\"command_index\":" << 4 << ",\"untimed_verifications\":[";
            for (int role_index = 0; role_index < 2; ++role_index) {
                const char *role = roles[role_index];
                const uint64_t began = Now();
                launch(role, "formal");
                Check(aclrtSynchronizeStream(stream), "untimed verification launch synchronize");
                snapshot(role, stream, buffers);
                Check(aclrtSynchronizeStream(stream), "untimed snapshot synchronize");
                identity.Verify();
                if (role_index) fields << ',';
                fields << "{\"role\":" << Quote(role) << ",\"implementation\":" << Quote(role)
                    << ",\"started_monotonic_ns\":" << began << ",\"finished_monotonic_ns\":" << Now()
                    << ",\"scope\":\"untimed_callback_verification\"}";
            }
            fields << ']';
            for (size_t i = 0; i < buffers.inputs.size(); ++i) {
                const auto &span = buffers.inputs[i];
                std::vector<unsigned char> after(span.bytes);
                Check(aclrtMemcpy(after.data(), span.bytes, span.data, span.bytes, ACL_MEMCPY_DEVICE_TO_HOST),
                      "verify immutable input");
                if (after != original_inputs[i]) throw std::runtime_error("shared callback modified input bytes");
            }
            fields << ",\"input_bytes_unchanged\":true,\"pilot_samples\":3";
            emit("complete", fields.str());
            return;
    }

    const char *phases[] = {"aa_before", "formal", "aa_after"};
    int phase_index = 0, next_pair = 0;
    bool primed = false;
    uint64_t next_command = 0;
    std::string text;
    while (std::getline(*commands, text)) {
        if (text.size() > 256) throw std::invalid_argument("oversized shared timing command");
        std::istringstream command(text);
        std::string action, phase;
        uint64_t index;
        if (!(command >> action >> index) || index != next_command)
            throw std::invalid_argument("shared timing command index differs");
        identity.Verify();
        if (action == "finish") {
            NoExtra(command);
            if (phase_index != 3 || primed || next_pair)
                throw std::invalid_argument("shared timing cannot finish an incomplete cycle");
            std::ostringstream fields;
            fields << ",\"command_index\":" << index << ",\"untimed_verifications\":[";
            for (int role_index = 0; role_index < 2; ++role_index) {
                const char *role = roles[role_index];
                const uint64_t began = Now();
                launch(role, "formal");
                Check(aclrtSynchronizeStream(stream), "untimed verification launch synchronize");
                snapshot(role, stream, buffers);
                Check(aclrtSynchronizeStream(stream), "untimed snapshot synchronize");
                identity.Verify();
                if (role_index) fields << ',';
                fields << "{\"role\":" << Quote(role) << ",\"implementation\":" << Quote(role)
                    << ",\"started_monotonic_ns\":" << began << ",\"finished_monotonic_ns\":" << Now()
                    << ",\"scope\":\"untimed_callback_verification\"}";
            }
            fields << ']';
            for (size_t i = 0; i < buffers.inputs.size(); ++i) {
                const auto &span = buffers.inputs[i];
                std::vector<unsigned char> after(span.bytes);
                Check(aclrtMemcpy(after.data(), span.bytes, span.data, span.bytes, ACL_MEMCPY_DEVICE_TO_HOST),
                      "verify immutable input");
                if (after != original_inputs[i]) throw std::runtime_error("shared callback modified input bytes");
            }
            fields << ",\"input_bytes_unchanged\":true,\"pairs_per_phase\":5";
            emit("complete", fields.str());
            return;
        }
        if (!(command >> phase) || phase_index >= 3 || phase != phases[phase_index])
            throw std::invalid_argument("shared timing phase differs");
        if (action == "prime") {
            NoExtra(command);
            if (primed || next_pair) throw std::invalid_argument("shared timing phase already primed");
            const uint64_t began = Now();
            const int order[] = {cycle_index % 2, 1 - cycle_index % 2, 1 - cycle_index % 2, cycle_index % 2};
            for (int slot : order)
                for (int i = 0; i < kPrime; ++i) launch(roles[slot], phase);
            Check(aclrtSynchronizeStream(stream), "prime synchronize");
            const uint64_t finished = Now();
            std::ostringstream fields;
            fields << ",\"command_index\":" << index << ",\"phase\":" << Quote(phase)
                << ",\"started_monotonic_ns\":" << began << ",\"finished_monotonic_ns\":" << finished
                << ",\"prime_order\":[";
            for (int i = 0; i < 4; ++i) { if (i) fields << ','; fields << Quote(roles[order[i]]); }
            fields << ']';
            emit("prime", fields.str());
            primed = true;
        } else if (action == "pair") {
            int pair_index;
            if (!(command >> pair_index) || !primed || pair_index != next_pair || pair_index >= kPairs)
                throw std::invalid_argument("shared timing pair index differs");
            NoExtra(command);
            const uint64_t began = Now();
            const int first = (cycle_index + pair_index) % 2;
            Sample samples[2];
            for (int slot = 0; slot < 2; ++slot) {
                const int role_index = (first + slot) % 2;
                if (phase == "formal" && role_index == 1)
                    samples[role_index] = measure(candidate, "candidate", candidate_launches);
                else samples[role_index] = measure(baseline, "baseline", baseline_launches);
            }
            std::ostringstream fields;
            fields << ",\"command_index\":" << index << ",\"phase\":" << Quote(phase)
                << ",\"pair_index\":" << pair_index << ",\"order\":[" << Quote(roles[first]) << ',' << Quote(roles[1-first]) << ']'
                << ",\"started_monotonic_ns\":" << began << ",\"finished_monotonic_ns\":" << Now()
                << ",\"baseline\":";
            WriteSample(fields, samples[0]);
            fields << ",\"candidate\":"; WriteSample(fields, samples[1]);
            emit("pair", fields.str());
            if (++next_pair == kPairs) { ++phase_index; next_pair = 0; primed = false; }
        } else throw std::invalid_argument("unknown shared timing command");
        ++next_command;
    }
    throw std::runtime_error("shared timing input ended before finish");
}
} // namespace aprof
#endif
