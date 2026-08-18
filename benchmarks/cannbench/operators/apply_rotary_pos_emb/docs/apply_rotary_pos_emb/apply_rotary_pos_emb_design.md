# ApplyRotaryPosEmb design
Each AIV core owns contiguous head rows. For each row, q/k and the selected sequence's cos/sin
are copied from GM into UB and vector-cast to FP32. Scalar FP32 UB reads map half or interleaved
partners; two volatile product temporaries preserve golden's separately rounded multiply-then-add
order. Results are vector-cast to the source dtype and DMA-written to both outputs. The largest
supported case here has D=128, so all live buffers are far below UB capacity. This correctness-first
row design covers both layouts and modes; performance optimization is intentionally deferred.
