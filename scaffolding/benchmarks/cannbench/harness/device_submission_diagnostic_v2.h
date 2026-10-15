#ifndef APROF_DEVICE_SUBMISSION_DIAGNOSTIC_V2_H
#define APROF_DEVICE_SUBMISSION_DIAGNOSTIC_V2_H
// Diagnostic fork of the frozen shared v2 header; never a measurement admission.
// The original direct-enqueue call order is preserved. Boundary observations and
// 73 fixed checkpoints perturb host execution and are diagnostic evidence only.
// No output, extra ACL calls, or synchronization is added inside a sample.
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
#include <sys/resource.h>
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
constexpr int kRepeat = 7300, kCheckpointInterval = 100;
constexpr size_t kCheckpointCount = kRepeat / kCheckpointInterval;
static_assert(kCheckpointCount == 73, "diagnostic checkpoint count must remain frozen");
constexpr const char *kProtocol = "shared_buffer_submission_diagnostic_v2";
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
inline uint64_t ThreadCpu() {
    struct timespec value {};
    if (clock_gettime(CLOCK_THREAD_CPUTIME_ID, &value) != 0)
        throw std::runtime_error("diagnostic thread CPU clock failed");
    return static_cast<uint64_t>(value.tv_sec) * 1000000000ULL + static_cast<uint64_t>(value.tv_nsec);
}
struct Observation {
    uint64_t wall_ns, thread_cpu_ns;
    struct rusage usage {};
};
inline Observation Observe() {
    Observation result;
    result.wall_ns = Now();
    result.thread_cpu_ns = ThreadCpu();
    if (getrusage(RUSAGE_THREAD, &result.usage) != 0)
        throw std::runtime_error("diagnostic thread resource observation failed");
    return result;
}
struct Segment {
    Observation before, after;
};
struct EnqueueCheckpoint {
    size_t completed_launches;
    uint64_t wall_ns, thread_cpu_ns;
};
inline uint64_t TimevalNs(const struct timeval &value) {
    return static_cast<uint64_t>(value.tv_sec) * 1000000000ULL
        + static_cast<uint64_t>(value.tv_usec) * 1000ULL;
}
inline void WriteObservation(std::ostream &out, const Observation &value) {
    out << "{\"wall_ns\":" << value.wall_ns << ",\"thread_cpu_ns\":" << value.thread_cpu_ns
        << ",\"rusage\":{\"utime_ns\":" << TimevalNs(value.usage.ru_utime)
        << ",\"stime_ns\":" << TimevalNs(value.usage.ru_stime)
        << ",\"minflt\":" << value.usage.ru_minflt << ",\"majflt\":" << value.usage.ru_majflt
        << ",\"nvcsw\":" << value.usage.ru_nvcsw << ",\"nivcsw\":" << value.usage.ru_nivcsw << "}}";
}
inline void WriteSegment(std::ostream &out, const Segment &segment) {
    out << "{\"before\":"; WriteObservation(out, segment.before);
    out << ",\"after\":"; WriteObservation(out, segment.after);
    out << '}';
}
struct Sample {
    const char *implementation;
    size_t launches;
    float milliseconds;
    double nanoseconds;
    uint64_t started, finished;
    int cpu_before, cpu_after;
    Segment start_record, enqueue, end_record, sync;
    std::array<EnqueueCheckpoint, kCheckpointCount> enqueue_checkpoints {};
};
inline void WriteSample(std::ostream &out, const Sample &sample) {
    out << "{\"implementation\":" << Quote(sample.implementation)
        << ",\"launches_per_operator\":" << sample.launches
        << ",\"elapsed_ms\":" << std::setprecision(17) << static_cast<double>(sample.milliseconds)
        << ",\"elapsed_ns\":" << sample.nanoseconds
        << ",\"started_monotonic_ns\":" << sample.started
        << ",\"finished_monotonic_ns\":" << sample.finished
        << ",\"cpu_before\":" << sample.cpu_before << ",\"cpu_after\":" << sample.cpu_after
        << ",\"submission_diagnostic\":{\"schema_version\":1,\"checkpoint_interval\":" << kCheckpointInterval
        << ",\"segments\":{\"start_record\":";
    WriteSegment(out, sample.start_record);
    out << ",\"enqueue\":"; WriteSegment(out, sample.enqueue);
    out << ",\"end_record\":"; WriteSegment(out, sample.end_record);
    out << ",\"sync\":"; WriteSegment(out, sample.sync);
    out << "},\"enqueue_checkpoints\":[";
    for (size_t i = 0; i < sample.enqueue_checkpoints.size(); ++i) {
        if (i) out << ',';
        const auto &checkpoint = sample.enqueue_checkpoints[i];
        out << "{\"completed_launches\":" << checkpoint.completed_launches
            << ",\"wall_ns\":" << checkpoint.wall_ns << ",\"thread_cpu_ns\":" << checkpoint.thread_cpu_ns << '}';
    }
    out << "]}}";
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
    if (!stream || !operator_name || std::string(operator_name) != "exp" || cycle_index < 0 || cycle_index >= 6
            || baseline_launches != 1 || candidate_launches != 1
            || !role_symbols[0] || !*role_symbols[0] || !role_symbols[1] || !*role_symbols[1])
        throw std::invalid_argument("invalid shared timing identity or complete-call launch counts");
    // This fixed diagnostic does not calibrate, admit, or retry a measurement.
    const char *mode_text = std::getenv("APROF_SHARED_MODE");
    const char *repeat_text = std::getenv("APROF_SHARED_REPEAT");
    if (!mode_text || std::string(mode_text) != "confirmation"
            || !repeat_text || std::string(repeat_text) != "7300")
        throw std::invalid_argument("diagnostic requires confirmation mode and repeat 7300");
    const std::string mode("confirmation");
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
            << ",\"diagnostic_only\":true,\"measurement_admission_eligible\":false"
            << ",\"cycle_index\":" << cycle_index << ",\"pid\":" << identity.pid
            << ",\"device\":" << identity.device << ",\"context_address\":" << Address(identity.context)
            << ",\"stream_address\":" << Address(stream)
            << ",\"warmup\":10,\"repeat\":" << kRepeat << ",\"prime_repeat\":100,\"execution_mode\":\"direct_enqueue\",\"mode\":" << Quote(mode)
            << ",\"warmup_role_counts\":{\"baseline\":10,\"candidate\":10}"
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
    for (int slot = 0; slot < 2; ++slot) {
        const char *role = roles[(slot + cycle_index) % 2];
        for (int i = 0; i < kWarmup; ++i) launch(role, "formal");
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
        sample.start_record.before = Observe();
        Check(aclrtRecordEvent(start.value, stream), "record start");
        sample.start_record.after = Observe();
        sample.enqueue.before = Observe();
        // Retain direct enqueue. Fixed-size checkpoints only observe host clocks;
        // no output, allocation, ACL call or synchronization occurs here.
        for (int i = 0; i < kRepeat; ++i) {
            callback(stream, buffers);
            if ((i + 1) % kCheckpointInterval == 0) {
                auto &checkpoint = sample.enqueue_checkpoints[(i + 1) / kCheckpointInterval - 1];
                checkpoint.completed_launches = static_cast<size_t>(i + 1);
                checkpoint.wall_ns = Now();
                checkpoint.thread_cpu_ns = ThreadCpu();
            }
        }
        sample.enqueue.after = Observe();
        sample.end_record.before = Observe();
        Check(aclrtRecordEvent(end.value, stream), "record end");
        sample.end_record.after = Observe();
        sample.sync.before = Observe();
        Check(aclrtSynchronizeEvent(end.value), "sample synchronize");
        sample.sync.after = Observe();
        Check(aclrtEventElapsedTime(&sample.milliseconds, start.value, end.value), "event elapsed time");
        sample.nanoseconds = static_cast<double>(sample.milliseconds) * 1000000.0 / kRepeat;
        sample.finished = Now();
        sample.cpu_after = Cpu();
        if (!std::isfinite(sample.nanoseconds) || sample.nanoseconds <= 0)
            throw std::runtime_error("nonpositive or nonfinite shared timing sample");
        identity.Verify();
        return sample;
    };

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
