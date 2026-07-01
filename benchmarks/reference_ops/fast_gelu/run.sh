#!/bin/bash

set -e

if [ -z "${ASCEND_HOME_PATH:-}" ]; then
    echo "[ERROR] CANN environment not set."
    echo "        Please run: source scripts/setup_env.sh"
    exit 1
fi

SKIP_BUILD=false
if [ "${1:-}" = "--skip-build" ]; then
    SKIP_BUILD=true
    shift
fi

M=${1:-8}
N=${2:-2048}
DTYPE=${3:-fp32}
CORES=${4:-1}

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

mkdir -p build data build/output

if [ "$SKIP_BUILD" = false ]; then
    echo "============================================"
    echo "[STEP 1/4] Building FastGelu direct-invoke executable..."
    echo "============================================"
    cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
    cmake --build build -j"$(nproc)"
else
    echo "[INFO] Skipping build (--skip-build)."
    if [ ! -x build/fast_gelu ]; then
        echo "[ERROR] build/fast_gelu does not exist. Run without --skip-build first."
        exit 1
    fi
fi

echo ""
echo "============================================"
echo "[STEP 2/4] Generating FP32 test data..."
echo "============================================"
python3 scripts/gen_data.py "$M" "$N" "$DTYPE"

echo ""
echo "============================================"
echo "[STEP 3/4] Running FastGelu kernel..."
echo "============================================"
rm -f build/output/output.bin
(
    cd build
    ./fast_gelu "$M" "$N" "$DTYPE" "$CORES"
)

echo ""
echo "============================================"
echo "[STEP 4/4] Verifying result..."
echo "============================================"
python3 scripts/verify_result.py "$DTYPE"

echo ""
echo "============================================"
echo "All steps completed."
echo "============================================"
