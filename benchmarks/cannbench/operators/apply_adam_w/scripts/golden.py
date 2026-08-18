import numpy as np


def apply_adam_w(var, grad, m, v, attrs):
    beta1 = np.float32(attrs["beta1"])
    beta2 = np.float32(attrs["beta2"])
    step = int(attrs.get("step", 1))
    m_new = beta1 * m + np.float32(1.0 - attrs["beta1"]) * grad
    v_new = beta2 * v + np.float32(1.0 - attrs["beta2"]) * grad * grad
    m_hat = m_new * np.float32(1.0 / np.float32(1.0 - float(attrs["beta1"]) ** step))
    v_hat = v_new * np.float32(1.0 / np.float32(1.0 - float(attrs["beta2"]) ** step))
    with np.errstate(all="ignore"):
        update = m_hat / (np.sqrt(v_hat) + np.float32(attrs.get("epsilon", 1e-8)))
    if attrs["weight_decay"] != 0:
        update = update + np.float32(attrs["weight_decay"]) * var
    sign = np.float32(attrs["lr"] if attrs.get("maximize", False) else -attrs["lr"])
    return var + sign * update
