#ifndef APROF_BENCH_DATA_UTILS_H
#define APROF_BENCH_DATA_UTILS_H

#include <cstdint>
#include <cstdio>
#include <stdexcept>
#include <string>
#include <vector>

inline std::vector<uint8_t> ReadBinaryFile(const std::string &path, size_t size)
{
    FILE *fp = fopen(path.c_str(), "rb");
    if (fp == nullptr) {
        throw std::runtime_error("open failed: " + path);
    }
    std::vector<uint8_t> data(size);
    size_t got = fread(data.data(), 1, size, fp);
    fclose(fp);
    if (got != size) {
        throw std::runtime_error("short read: " + path);
    }
    return data;
}

inline void WriteBinaryFile(const std::string &path, const std::vector<uint8_t> &data)
{
    FILE *fp = fopen(path.c_str(), "wb");
    if (fp == nullptr) {
        throw std::runtime_error("open failed: " + path);
    }
    size_t wrote = fwrite(data.data(), 1, data.size(), fp);
    fclose(fp);
    if (wrote != data.size()) {
        throw std::runtime_error("short write: " + path);
    }
}

#endif
