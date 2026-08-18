#!/usr/bin/env python3
import argparse, json
from pathlib import Path
import numpy as np, torch
from torch.nn import functional as F

RAW = {'float16': np.float16, 'bfloat16': np.uint16}
def tensor(path, shape, dtype):
    a = np.memmap(path, RAW[dtype], 'r', shape=tuple(shape)); t = torch.from_numpy(np.asarray(a).copy()); return t.view(torch.bfloat16) if dtype == 'bfloat16' else t
def main():
    p = argparse.ArgumentParser(); p.add_argument('--metadata', required=True); args = p.parse_args(); mp = Path(args.metadata); m = json.loads(mp.read_text()); dt = m['dtype']; at = m['attrs']
    x = tensor(m['x'], m['x_shape'], dt); grad = tensor(m['grad'], m['grad_shape'], dt); actual = tensor(m['output'], m['output_shape'], dt)
    reference = F.grad.conv3d_weight(x, tuple(at['filter_size']), grad, stride=tuple(at['strides']), padding=(at['pads'][0], at['pads'][2], at['pads'][4]), dilation=tuple(at['dilations']), groups=at['groups'])
    expected_fp32 = F.grad.conv3d_weight(x.float(), tuple(at['filter_size']), grad.float(), stride=tuple(at['strides']), padding=(at['pads'][0], at['pads'][2], at['pads'][4]), dilation=tuple(at['dilations']), groups=at['groups'])
    expected = expected_fp32.to(x.dtype)
    sum_abs = F.grad.conv3d_weight(x.float().abs(), tuple(at['filter_size']), grad.float().abs(), stride=tuple(at['strides']), padding=(at['pads'][0], at['pads'][2], at['pads'][4]), dilation=tuple(at['dilations']), groups=at['groups'])
    kd, kh, kw = at['filter_size'][2:]; sd, sh, sw = at['strides']; dd, dh, dw = at['dilations']; pf, pt, pl = at['pads'][0], at['pads'][2], at['pads'][4]
    counts = np.zeros((kd, kh, kw), np.float32)
    for kz in range(kd):
        cz = sum(0 <= oz * sd + kz * dd - pf < m['x_shape'][2] for oz in range(m['grad_shape'][2]))
        for ky in range(kh):
            cy = sum(0 <= oy * sh + ky * dh - pt < m['x_shape'][3] for oy in range(m['grad_shape'][3]))
            for kx in range(kw):
                cx = sum(0 <= ox * sw + kx * dw - pl < m['x_shape'][4] for ox in range(m['grad_shape'][4]))
                counts[kz, ky, kx] = m['x_shape'][0] * cz * cy * cx
    eps = np.finfo(np.float32).eps; gamma = (counts * eps) / (1.0 - counts * eps)
    forward_bound = 2.0 * gamma[None, None, :, :, :] * sum_abs.numpy()
    got, gold = actual.float().numpy(), expected.float().numpy()
    special = bool(np.array_equal(np.isnan(got), np.isnan(gold)) and np.array_equal(np.isposinf(got), np.isposinf(gold)) and np.array_equal(np.isneginf(got), np.isneginf(gold)))
    finite = np.isfinite(got) & np.isfinite(gold); thr = {'float16': 2**-10, 'bfloat16': 2**-7}[dt]
    absolute_floor = 2**-5
    if finite.any():
        diff = np.abs(got[finite] - gold[finite]); amax = float(diff.max())
        raw_rel = diff / (np.abs(gold[finite]) + 1e-7); raw_mere = float(raw_rel.mean(dtype=np.float64)); raw_mare = float(raw_rel.max())
        pos = torch.nextafter(expected, torch.full_like(expected, float('inf'))).float(); neg = torch.nextafter(expected, torch.full_like(expected, float('-inf'))).float()
        ulp = torch.maximum((pos - expected.float()).abs(), (expected.float() - neg).abs()).numpy()[finite]
        local_equiv = diff <= np.maximum(ulp, absolute_floor); bound_finite = forward_bound[finite]
        ill_conditioned = (~local_equiv) & (np.abs(gold[finite]) <= bound_finite) & (diff <= bound_finite)
        rel = np.where(local_equiv | ill_conditioned, 0.0, raw_rel); mere = float(rel.mean(dtype=np.float64)); mare = float(rel.max())
        ill_count = int(ill_conditioned.sum()); max_bound_ratio = float((diff[ill_conditioned] / bound_finite[ill_conditioned]).max()) if ill_count else 0.0
    else: amax = raw_mere = raw_mare = mere = mare = max_bound_ratio = 0.0; ill_count = 0
    ref = reference.float().numpy(); ref_finite = np.isfinite(got) & np.isfinite(ref); ref_special = bool(np.array_equal(np.isnan(got), np.isnan(ref)) and np.array_equal(np.isposinf(got), np.isposinf(ref)) and np.array_equal(np.isneginf(got), np.isneginf(ref)))
    if ref_finite.any():
        ref_diff = np.abs(got[ref_finite] - ref[ref_finite]); ref_rel = ref_diff / (np.abs(ref[ref_finite]) + 1e-7); ref_mere = float(ref_rel.mean(dtype=np.float64)); ref_mare = float(ref_rel.max()); ref_max_abs = float(ref_diff.max())
    else: ref_mere = ref_mare = ref_max_abs = 0.0
    passed = bool(special and mere < thr and mare < 10 * thr and max_bound_ratio <= 1.0)
    result = {'case_id': m['case_id'], 'x_shape': m['x_shape'], 'grad_shape': m['grad_shape'], 'output_shape': m['output_shape'], 'dtype': dt, 'attrs': at, 'note': m['note'], 'numel': m['numel'],
              'kernel_us': None, 'max_abs_error': amax, 'raw_mere': raw_mere, 'raw_mare': raw_mare, 'absolute_error_floor': absolute_floor,
              'mere': mere, 'mare': mare, 'threshold': thr, 'one_ulp_equivalence': True,
              'forward_error_rule': 'ill-conditioned only: abs(oracle)<=2*gamma_K*sum_abs_products and abs(device-oracle)<=same bound',
              'ill_conditioned_count': ill_count, 'max_bound_ratio': max_bound_ratio, 'special_values_match': special,
              'exact_match': bool(np.array_equal(got, gold, equal_nan=True)),
              'primary_oracle': 'torch_float32_conv3d_weight_then_single_output_cast',
              'native_dtype_reference_diagnostic': {'max_abs_error': ref_max_abs, 'mere': ref_mere, 'mare': ref_mare, 'special_values_match': ref_special, 'exact_match': bool(np.array_equal(got, ref, equal_nan=True))},
              'passed': passed}
    (mp.parent / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=True)); print(json.dumps(result, allow_nan=True)); raise SystemExit(0 if passed else 1)
if __name__ == '__main__': main()
