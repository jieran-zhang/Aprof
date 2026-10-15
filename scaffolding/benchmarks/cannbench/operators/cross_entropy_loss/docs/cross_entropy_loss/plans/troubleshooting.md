# CrossEntropyLoss troubleshooting

## [Phase 7] Vector dependency and C=16384 UB overflow

Initial hardware tests showed large numerical errors and ACL 507035 at float32 C=16384. The
Adds/Exp/ReduceSum/Ln chain lacked V-pipe dependency barriers, and float32 unnecessarily allocated
the non-float cast buffer, pushing UB above budget. Explicit barriers were added between dependent
vector operations; `fpBuf_` allocation/access is now guarded by the same non-float `if constexpr`.

## [Phase 7] Strided channel gather via scalar GM reads

2D cases passed after reduction fixes, while 4D NCHW still failed. The address formula was correct,
but scalar GM `GetValue` was unreliable for the strided C axis. The gather now issues 32-byte
multi-block DMA transfers with source stride `inner-lanes`, then extracts the same lane from each
class block. This preserves `((n*C+c)*inner)+innerIdx` for all channel-first ranks.

## [Phase 7] Scalar GM access and reduced-output architecture

`reduction=none` isolated the per-position log-sum-exp path as correct, while multi-core mean/sum
lost workspace entries. Direct GM scalar reads/writes and 4-byte `DataCopyPad` operations are not a
safe cross-core FP32 workspace protocol on dav-2201: DMA writes have 32-byte granularity and can
overlap adjacent positions. Mean and sum therefore use a dedicated single-AICore kernel that walks
all positions, accumulates loss/count in FP32, and writes the final output once. `none` retains the
multi-core per-position path and does not allocate a logical reduction workspace.

The selected target logit also must not use a direct GM scalar read followed by a half/BF16 scalar
cast. The implementation first performs the channel gather, vector-casts it to packed FP32 when
needed, reads `v[label]` before the in-place subtract/exp sequence, and then computes the stable
log-sum-exp. Hardware regressions for FP16, BF16, and strided FP32 all passed with this path.
