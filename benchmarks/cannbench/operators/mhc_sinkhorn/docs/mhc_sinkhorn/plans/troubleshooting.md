# Troubleshooting

## [Phase 6] Exp count requires a local signed scalar

**现象：** Build rejected passing `t_->n` directly as vector API count.
**根因：** `AscendC::Exp/Adds` require `const int32_t&`, while tiling resides in GM as
`uint32_t`.
**解决方案：** Copy width to a local `int32_t` before vector calls.
**预防：** Materialize vector counts in local signed scalars.

## [Phase 7] Unaligned UB row causes ACL 507035

**现象：** Initial case 1 launch failed with ACL `507035`.
**根因：** A compact 4×4 matrix places row 1 at byte offset 16, but vector `Exp`
requires each UB row address to be 32-byte aligned.
**解决方案：** Device kernel now loads compact raw UB, repacks to a compute UB with
row stride `align_up(N,8)`, computes there, then compacts before GM output.
**经验：** Small rows still require vector-address alignment independent of count.
**预防：** Align every independently vectorized UB row to 32 bytes.
