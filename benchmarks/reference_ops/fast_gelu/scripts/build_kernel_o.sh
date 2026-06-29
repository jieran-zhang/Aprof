#!/usr/bin/env bash
# Build device-side kernel .o for msprof op simulator --config.
set -euo pipefail

OP_NAME=${1:-fast_gelu}
KERNEL_SRC=${2:-op_kernel/${OP_NAME}_kernel.asc}
OUT_DIR=${3:-build_sim}
NPU_ARCH=${4:-dav-3510}

: "${ASCEND_HOME_PATH:?ASCEND_HOME_PATH not set; run 'source scripts/setup_env.sh' first}"

BISHENG="$ASCEND_HOME_PATH/bin/bisheng"
LD="$ASCEND_HOME_PATH/bin/ld.lld"

mkdir -p "$OUT_DIR"
OBJ="$OUT_DIR/${OP_NAME}_kernel.obj"
ELF="$OUT_DIR/${OP_NAME}_kernel.o"

echo "[INFO] Compiling $KERNEL_SRC -> $OBJ (npu-arch=$NPU_ARCH)"
"$BISHENG" -fPIC --aicore-only --npu-arch="$NPU_ARCH" -O2 -g \
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
file "$ELF"
