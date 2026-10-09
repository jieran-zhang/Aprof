#pragma once
#include <fstream>
#include <string>
inline bool ReadFile(const std::string &path, void *data, size_t bytes) {
    std::ifstream in(path, std::ios::binary); return in && bool(in.read(static_cast<char *>(data), bytes));
}
inline bool WriteFile(const std::string &path, const void *data, size_t bytes) {
    std::ofstream out(path, std::ios::binary); return out && bool(out.write(static_cast<const char *>(data), bytes));
}
