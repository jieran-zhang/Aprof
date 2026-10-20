#pragma once

#include <acl/acl_prof.h>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <stdexcept>
#include <string>

namespace aprof {

// Construct after aclInit; finish before the caller resets the device or calls aclFinalize.
class TaskProfile {
public:
    TaskProfile() {
        const char *value = std::getenv("APROF_TASK_PROFILE_DIR");
        if (!value) return;
        if (!*value)
            throw std::invalid_argument("APROF_TASK_PROFILE_DIR cannot be empty");
        const std::filesystem::path directory(value);
        if (!directory.is_absolute() || std::filesystem::is_symlink(directory) ||
            !std::filesystem::is_directory(directory) || !std::filesystem::is_empty(directory))
            throw std::invalid_argument("APROF_TASK_PROFILE_DIR must be an absolute empty directory");
        directory_ = directory.string();
        Check(aclprofInit(directory_.c_str(), directory_.size()), "aclprofInit");
        initialized_ = true;
        enabled_ = true;
    }

    TaskProfile(const TaskProfile &) = delete;
    TaskProfile &operator=(const TaskProfile &) = delete;

    void Start(uint32_t device) {
        if (!enabled_) return;
        if (!initialized_ || config_ || started_)
            throw std::logic_error("TaskProfile.Start requires one fresh initialized session");
        config_ = aclprofCreateConfig(&device, 1, ACL_AICORE_NONE, nullptr, ACL_PROF_TASK_TIME);
        if (!config_)
            throw std::runtime_error("aclprofCreateConfig returned null");
        Check(aclprofStart(config_), "aclprofStart");
        started_ = true;
    }

    void Finish() {
        if (!enabled_) return;
        if (!started_)
            throw std::logic_error("TaskProfile.Finish requires an active session");
        const Failure failure = Cleanup();
        if (failure.operation)
            Check(failure.code, failure.operation);
    }

    ~TaskProfile() noexcept { Cleanup(); }

private:
    struct Failure {
        const char *operation = nullptr;
        aclError code = ACL_SUCCESS;
    };

    static void Check(aclError code, const char *operation) {
        if (code != ACL_SUCCESS)
            throw std::runtime_error(std::string(operation) + " failed: " +
                                     std::to_string(static_cast<long long>(code)));
    }

    Failure Cleanup() noexcept {
        Failure first;
        auto record = [&](aclError code, const char *operation) {
            if (code == ACL_SUCCESS) return;
            std::fprintf(stderr, "%s cleanup failed: %lld\n", operation, static_cast<long long>(code));
            if (!first.operation) first = {operation, code};
        };
        // Continue releasing the remaining resources even if one cleanup call fails.
        if (started_) {
            started_ = false;
            record(aclprofStop(config_), "aclprofStop");
        }
        if (config_) {
            const aclprofConfig *config = config_;
            config_ = nullptr;
            record(aclprofDestroyConfig(config), "aclprofDestroyConfig");
        }
        if (initialized_) {
            initialized_ = false;
            record(aclprofFinalize(), "aclprofFinalize");
        }
        return first;
    }

    std::string directory_;
    aclprofConfig *config_ = nullptr;
    bool initialized_ = false;
    bool started_ = false;
    bool enabled_ = false;
};

}  // namespace aprof
