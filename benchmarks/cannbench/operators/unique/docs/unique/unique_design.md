# Design

Unique has data-dependent output length. The host transfers only the original
input and allocates maximum-sized output/workspace buffers. Ascend C performs:

1. parallel conversion from each dtype to an order-preserving unsigned key;
2. a correctness-first LSD radix sort in global-memory ping-pong buffers;
3. NPU-side adjacent-key compaction, raw-value decoding, and unique count;
4. parallel NPU-side binary search to construct the optional inverse tensor.

Float key encoding normalizes signed zero and preserves exact source bits for
all other values. Signed integers flip the sign bit; IEEE floating values use
the standard complement/sign-bit transform. The host reads only the resulting
count, `y`, and inverse after the kernels finish. Radix passes intentionally
use one core for deterministic global scatter; this is a correctness-first
implementation with no performance optimization.
