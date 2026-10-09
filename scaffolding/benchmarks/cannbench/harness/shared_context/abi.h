#pragma once
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define SC_ABI_VERSION 1
/* The runner owns ACL/context/stream. Roles must not initialize/reset them. */
typedef struct { void *pointer; size_t bytes; const char *kind; } SCResource;
typedef struct {
 uint32_t abi_version;
 const char *role;
 const char *operator_name;
 const char *source_sha256;
 const char *kernel_symbols;
} SCIdentity;
typedef struct {
 uint32_t abi_version;
 const SCIdentity *(*identity)(void);
 int (*prepare)(int argc, char **argv, int64_t cores, void *stream, void **state);
 int (*launch)(void *state);
 int (*export_output)(void *state, const char *path);
 void (*destroy)(void *state);
 uint64_t (*launch_count)(void *state);
 SCResource *(*resources)(void *state, size_t *count);
 const char *(*error)(void);
} SCAPI;
typedef const SCAPI *(*SCGetAPI)(void);
#ifdef __cplusplus
}
#endif
