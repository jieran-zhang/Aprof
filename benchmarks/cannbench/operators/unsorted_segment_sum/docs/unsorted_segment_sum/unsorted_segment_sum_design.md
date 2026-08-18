# Design

The host zero-initializes a padded workspace and synchronizes before launch. A
single AICore walks rows in increasing `n`, reads the segment ID, and processes
the flattened tail in 4096-element tiles. Data and the target segment tile are
DMA-copied to UB, added there, and DMA-written back. Each workspace row uses an
aligned stride so a short 32-byte DMA tail cannot overwrite the next segment.
FP16/BF16 use FP32 workspace and vector casts; other dtypes retain their dtype.
A final single-core pass walks segments in order and DMA-packs the padded rows
into the compact output. Single-core execution removes atomic and ordering
hazards and matches golden input order.

This correctness-first path is O(data.numel), requires no atomics or segment
sorting, and supports ranks 1-8 because all tail dimensions are flattened.
