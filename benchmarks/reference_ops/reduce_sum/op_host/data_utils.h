#ifndef DATA_UTILS_H
#define DATA_UTILS_H

#include <cstdio>
#include <cstdlib>
#include <string>

inline void ReadBinaryFile(const std::string& path, void* buffer, size_t expected)
{
    FILE* fp = fopen(path.c_str(), "rb");
    if (fp == nullptr) {
        fprintf(stderr, "[ERROR] Cannot open %s for reading\n", path.c_str());
        exit(1);
    }

    fseek(fp, 0, SEEK_END);
    long fileSize = ftell(fp);
    fseek(fp, 0, SEEK_SET);

    if (fileSize < 0 || static_cast<size_t>(fileSize) < expected) {
        fprintf(stderr, "[ERROR] File %s too small: got %ld bytes, expected %zu\n",
                path.c_str(), fileSize, expected);
        fclose(fp);
        exit(1);
    }

    size_t readBytes = fread(buffer, 1, expected, fp);
    if (readBytes != expected) {
        fprintf(stderr, "[ERROR] Read %zu bytes from %s, expected %zu\n",
                readBytes, path.c_str(), expected);
        fclose(fp);
        exit(1);
    }

    fclose(fp);
}

inline void WriteBinaryFile(const std::string& path, const void* buffer, size_t size)
{
    FILE* fp = fopen(path.c_str(), "wb");
    if (fp == nullptr) {
        fprintf(stderr, "[ERROR] Cannot open %s for writing\n", path.c_str());
        exit(1);
    }

    size_t written = fwrite(buffer, 1, size, fp);
    if (written != size) {
        fprintf(stderr, "[ERROR] Wrote %zu bytes to %s, expected %zu\n", written, path.c_str(), size);
        fclose(fp);
        exit(1);
    }

    fclose(fp);
}

#endif // DATA_UTILS_H
