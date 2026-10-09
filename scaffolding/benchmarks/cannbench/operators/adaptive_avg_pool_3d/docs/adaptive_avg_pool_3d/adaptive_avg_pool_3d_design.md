# Design

The output linear index space is split evenly across available vector cores.
Each core decodes `(n,c,od,oh,ow)`, computes exact integer start/end bounds,
and reads its input window directly from global memory. Float16 and bfloat16
values are widened to float32 in scalar code. Float32 results are stored
directly; 16-bit results are staged in a 4 KiB float UB tile, cast in batches,
then copied to global memory. The tail copy uses byte-granular `DataCopyPad`.

UB live storage per 1024-result tile is 4096 bytes for the float accumulator
and 2048 bytes for the converted output. There is no cross-core state and no
atomic operation. This deliberately favors a compact, robust correctness path
over performance optimization.
