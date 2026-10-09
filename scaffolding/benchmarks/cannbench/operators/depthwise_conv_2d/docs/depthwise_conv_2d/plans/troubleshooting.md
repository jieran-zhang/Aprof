# Troubleshooting

## 2026-08-12: ASC host compiler rejected nested initializer-list loops

- Symptom: `cannot use type 'void' as a range` around compact allocation loops.
- Root cause: bisheng could not deduce the heterogeneous nested initializer.
- Fix: spell out the nine ACL allocation calls explicitly.
- Prevention: avoid nested braced lists in `.asc` host code even when ordinary
  C++ compilers accept a similar form.
