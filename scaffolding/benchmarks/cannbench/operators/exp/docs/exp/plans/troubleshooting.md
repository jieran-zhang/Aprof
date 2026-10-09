# Troubleshooting

## `__gm__` scalar fields rejected by `Muls` / `Adds`

- Symptom: bisheng reported conflicting scalar types `float` and `__gm__ float`.
- Cause: passing a field of the GM-resident tiling struct directly to a vector API.
- Fix: copy `multiplier` and `shift` into device-local `float` variables first.
- Prevention: always materialize GM metadata scalars into local variables before
  passing them to templated AscendC compute APIs.
