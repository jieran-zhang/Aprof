#!/usr/bin/env bash
# Build a device-side Ascend C kernel .o for `msprof op simulator --config`.
#
# Usage:
#   bash build_kernel_o.sh <op_name> [<kernel_src>] [<output_dir>] [<npu_arch>]
#
# Defaults:
#   kernel_src = op_kernel/<op_name>_kernel.asc
#   output_dir = build_sim
#   npu_arch   = dav-3510   (Ascend950)
#
# Requires:
#   - $ASCEND_HOME_PATH set (source scripts/setup_env.sh first)
#   - bisheng + ld.lld in $ASCEND_HOME_PATH/bin/

set -euo pipefail

OP_NAME=${1:?usage: $0 <op_name> [<kernel_src>] [<output_dir>] [<npu_arch>]}
KERNEL_SRC=${2:-op_kernel/${OP_NAME}_kernel.asc}
OUT_DIR=${3:-build_sim}
NPU_ARCH=${4:-dav-3510}

: "${ASCEND_HOME_PATH:?ASCEND_HOME_PATH not set; run 'source scripts/setup_env.sh' first}"

BISHENG="$ASCEND_HOME_PATH/bin/bisheng"
LD="$ASCEND_HOME_PATH/bin/ld.lld"

[ -x "$BISHENG" ] || { echo "[ERROR] bisheng not found at $BISHENG"; exit 1; }
[ -x "$LD" ]      || { echo "[ERROR] ld.lld   not found at $LD"; exit 1; }
[ -f "$KERNEL_SRC" ] || { echo "[ERROR] kernel source not found: $KERNEL_SRC"; exit 1; }

mkdir -p "$OUT_DIR"
OBJ="$OUT_DIR/${OP_NAME}_kernel.obj"
ELF="$OUT_DIR/${OP_NAME}_kernel.o"

echo "[INFO] Compiling $KERNEL_SRC -> $OBJ (npu-arch=$NPU_ARCH)"
"$BISHENG" -fPIC --aicore-only --npu-arch="$NPU_ARCH" -O2 \
    -I op_kernel -I op_host \
    -I "$ASCEND_HOME_PATH/include" \
    -I "$ASCEND_HOME_PATH/x86_64-linux/include" \
    -I "$ASCEND_HOME_PATH/compiler/tikcpp/tikcfw" \
    -I "$ASCEND_HOME_PATH/compiler/tikcpp/tikcfw/impl" \
    -I "$ASCEND_HOME_PATH/compiler/tikcpp/tikcfw/interface" \
    --asc-aicore-lang -c "$KERNEL_SRC" \
    -o "$OBJ"

echo "[INFO] Linking $OBJ -> $ELF"
"$LD" -m aicorelinux -Ttext=0 "$OBJ" -static -o "$ELF"

echo "[INFO] Done. File info:"
file "$ELF"
echo
echo "[INFO] Expected: ELF 64-bit LSB executable, *unknown arch 0x1029*, statically linked"
echo "[INFO] Tip: re-run with extra '-g' in BISHENG cmd for source-line hotspot in *_code_exe_*.csv"
