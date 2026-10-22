## 数学定义

```text
m_new = beta1*m + (1-beta1)*grad
v_new = beta2*v + (1-beta2)*grad*grad
m_hat = m_new / (1-beta1**step)
v_hat = v_new / (1-beta2**step)
update = m_hat / (sqrt(v_hat)+epsilon) + weight_decay*var
y = var + lr*update  (maximize=true)
y = var - lr*update  (maximize=false)
```

`epsilon` 位于 sqrt 外部；输入 `var/grad/m/v` 不会被更新。

