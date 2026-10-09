# grouped_matmul

Direct-launch Ascend C grouped matrix multiplication for Ascend910_9362 (`dav-2201`).
The host performs only file I/O, allocation, tiling and kernel launch; all matrix products,
bias additions and sensitive-value correction execute in the locally compiled device image.

```bash
cmake -S . -B build && cmake --build build -j2
ASCEND_RT_VISIBLE_DEVICES=3 DEVICE=0 ./run.sh all
```
