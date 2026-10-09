# Mish flash design

The kernel splits the flattened tensor across available vector cores and
processes 2048 elements per tile. Input is converted to float32. Softplus is
computed without overflow as `max(x, 0) + log(1 + exp(-abs(x)))`; for `x < -8`
the equivalent `exp(x)` tail avoids cancellation in `log(1 + z)`. This is
followed by `tanh` and multiplication by the original input. The result is
converted back to the source dtype. UB contains raw input/output queues, three
float32 buffers (input, work, output), and one predicate mask, with at most 17
live bytes per element for float32 input.
