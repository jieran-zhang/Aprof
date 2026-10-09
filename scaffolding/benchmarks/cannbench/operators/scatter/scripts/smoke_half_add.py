#!/usr/bin/env python3
import argparse
import subprocess
import tempfile
from pathlib import Path
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--device', default='4')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='scatter_half_add_') as temp:
        directory = Path(temp)
        data = np.array([3.0, 4.0], dtype=np.float16)
        indices = np.array([0, 0], dtype=np.int32)
        updates = np.array([1.0, 2.0], dtype=np.float16)
        data.tofile(directory/'data.bin')
        indices.tofile(directory/'indices.bin')
        updates.tofile(directory/'updates.bin')
        command = [
            str(root/'build/scatter'), '--data-shape', '2', '--index-shape', '2',
            '--data-dtype', 'float16', '--index-dtype', 'int32', '--dim', '0',
            '--reduce', 'add', '--data', str(directory/'data.bin'),
            '--indices', str(directory/'indices.bin'), '--updates', str(directory/'updates.bin'),
            '--output', str(directory/'output.bin'), '--device', args.device,
        ]
        subprocess.run(command, check=True)
        output = np.fromfile(directory/'output.bin', dtype=np.float16)
        bits = output.view(np.uint16)
        print(f'output={output.tolist()} bits={[hex(int(value)) for value in bits]}')
        expected = np.array([6.0, 4.0], dtype=np.float16)
        if not np.array_equal(output, expected):
            raise SystemExit(f'expected {expected.tolist()}, got {output.tolist()}')
        print('PASS: duplicate-index half add is exact')


if __name__ == '__main__':
    main()
