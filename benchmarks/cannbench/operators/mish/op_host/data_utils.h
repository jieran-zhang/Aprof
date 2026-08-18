#pragma once
#include <filesystem>
#include <fstream>
#include <string>

inline bool ReadFile(const std::string &path, void *data, size_t bytes) {
    std::ifstream f(path, std::ios::binary);
    return f && static_cast<bool>(f.read(reinterpret_cast<char *>(data), bytes));
}

inline bool WriteFile(const std::string &path, const void *data, size_t bytes) {
    std::filesystem::path p(path);
    if (p.has_parent_path()) std::filesystem::create_directories(p.parent_path());
    std::ofstream f(path, std::ios::binary);
    return f && static_cast<bool>(f.write(reinterpret_cast<const char *>(data), bytes));
}
