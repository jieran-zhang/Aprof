# ApplyRotaryPosEmb definition
For query/key `[B,S,N,D]` or `[B,N,S,D]`, D even, each output is `x*cos + rotate(x)*sin`.
Half mode pairs dimensions `d` and `d+D/2`; interleaved mode pairs adjacent even/odd dimensions.
Cos/sin `(S,D/2)` broadcast over B,N, or `(B,S,D/2)` over N. FP16/BF16 inputs compute in FP32 then cast back; float32 remains float32.
