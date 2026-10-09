# Troubleshooting

## GM scalar RMW and final scalar writes

The first real-NPU version used DCache-bypass scalar read/modify/write for the
accumulator and final output. Cases 1-4 all lost many writes across float and
integer dtypes (MERE roughly 0.47-0.64 for floating cases), proving this was not
a conversion issue. The accumulator was replaced by row-tiled DMA to UB, UB
addition, and DMA writeback on one AICore.

Using scalar bypass only for the final compact output reproduced the same
metrics, so scalar GM writes were removed entirely. The final kernel now packs
each segment with DMA. Workspace rows have an aligned stride, and final segments
are written sequentially so any short tail's 32-byte granularity is overwritten
by the next segment's authoritative row. Cases 1-4 then passed exactly, followed
by all 20 original cases on real Ascend910 hardware.
