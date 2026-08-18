#pragma once
#include <fstream>
#include <string>

inline bool ReadFile(const std::string &path, void *data, size_t bytes) {
    std::ifstream f(path, std::ios::binary);
    if (!f) return false;
    f.read(static_cast<char *>(data), static_cast<std::streamsize>(bytes));
    return f.good() || static_cast<size_t>(f.gcount()) == bytes;
}

inline bool WriteFile(const std::string &path, const void *data, size_t bytes) {
    std::ofstream f(path, std::ios::binary);
    if (!f) return false;
    f.write(static_cast<const char *>(data), static_cast<std::streamsize>(bytes));
    return f.good();
}
