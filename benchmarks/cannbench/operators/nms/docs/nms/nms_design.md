# NMS design

One device vector core performs the inherently sequential greedy algorithm. An 8192-byte UB state array
marks processed or suppressed boxes. Every round scans device scores to choose the best unsuppressed
index, writes that index, then computes float32 intersection, union and IoU against remaining boxes and
updates UB state. The device writes both dynamic output indices and the retained count; host performs no
sorting, IoU, suppression, selection, or output precomputation.

NaN-aware scalar min/max reproduce `torch.maximum/minimum`; clamp preserves NaN. Maximum live UB is 8 KiB.
