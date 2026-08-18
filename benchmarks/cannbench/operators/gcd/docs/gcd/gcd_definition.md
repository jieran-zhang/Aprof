# gcd 定义

`gcd(x1, x2)` 对两个同 dtype 整数张量逐元素计算最大公约数，输入按 PyTorch
广播规则扩展，输出 shape 为广播 shape，dtype 保持为 `int16`、`int32` 或 `int64`。

对每个元素先取数学绝对值，再执行 Euclid 迭代 `while b != 0: (a,b)=(b,a%b)`。
`gcd(0,0)=0`，负数结果非负；唯一不能由有符号 dtype 表示的幅值是该 dtype 的
`abs(INT_MIN)`，此时按 `torch.gcd` 的二补码行为输出 `INT_MIN`。实现使用同位宽无符号
幅值避免求负时溢出，因而也覆盖 `INT_MIN`、零和负数。

CPU 参考为 `torch.gcd(*torch.broadcast_tensors(x1, x2))`，结果必须逐位完全相等。
