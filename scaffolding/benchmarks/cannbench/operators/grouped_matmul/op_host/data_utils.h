#pragma once
#include <cstddef>
#include <fstream>
#include <string>
inline bool ReadFile(const std::string &path, void *data, size_t bytes) {
    std::ifstream f(path, std::ios::binary); return f && bool(f.read(static_cast<char *>(data), bytes));
}
inline bool WriteFile(const std::string &path, const void *data, size_t bytes) {
    std::ofstream f(path, std::ios::binary); return f && bool(f.write(static_cast<const char *>(data), bytes));
}
