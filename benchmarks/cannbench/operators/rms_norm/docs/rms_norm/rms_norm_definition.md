# rms_norm 定义

对 `x` 的每个最后维行（长度 D）计算
`y_i = x_i * rsqrt(sum_j(float(x_j)^2)/D + epsilon) * gamma_i`。
gamma/weight shape 必须为 `(D,)` 且 dtype 与 x 相同；支持 float16、float32、bfloat16。
平方、求和、均值、rsqrt 和乘法均在 FP32 中完成，仅最终结果回转输入 dtype。
epsilon 必须为正数。零输入产生零；NaN 按 IEEE 传播；含 Inf 的行因 `Inf*0` 产生 NaN，
与 PyTorch `torch.nn.functional.rms_norm` golden 一致。
