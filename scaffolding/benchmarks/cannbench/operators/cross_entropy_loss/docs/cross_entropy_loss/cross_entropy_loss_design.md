# CrossEntropyLoss design
Each AIV core handles target positions. It gathers the strided C axis into UB, casts to FP32, performs stable max/exp/sum/log, and emits none output or FP32 core partial sum/count. A one-core finish kernel performs sum/mean and casts the scalar result. C is at most 16384. This is a correctness-first implementation without profiling or optimization.
