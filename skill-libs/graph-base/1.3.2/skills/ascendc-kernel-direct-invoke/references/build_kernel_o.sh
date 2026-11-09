#!/usr/bin/env bash
# Copyright (c) 2026 AProf contributors.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
# Build a device-side Ascend C kernel .o for `msprof op simulator --config`.
#
# Usage:
#   bash build_kernel_o.sh <op_name> [<kernel_src>] [<output_dir>] [<npu_arch>] [auto|aiv|aic]
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

OP_NAME=${1:?usage: $0 <op_name> [<kernel_src>] [<output_dir>] [<npu_arch>] [auto|aiv|aic]}
KERNEL_SRC=${2:-op_kernel/${OP_NAME}_kernel.asc}
OUT_DIR=${3:-build_sim}
NPU_ARCH=${4:-dav-3510}
CORE_TYPE=${5:-auto}

case "$CORE_TYPE" in
    auto) ARCH_FLAG="--npu-arch=$NPU_ARCH" ;;
    aiv|aic)
        if [ "$NPU_ARCH" != dav-2201 ]; then
            echo "[ERROR] explicit core selection is validated only for dav-2201; check the selected SDK"
            exit 1
        fi
        if [ "$CORE_TYPE" = aiv ]; then
            ARCH_FLAG=--cce-aicore-arch=dav-c220-vec
        else
            ARCH_FLAG=--cce-aicore-arch=dav-c220-cube
        fi
        ;;
    *) echo "[ERROR] core type must be auto, aiv or aic"; exit 1 ;;
esac

: "${ASCEND_HOME_PATH:?ASCEND_HOME_PATH not set; run 'source scripts/setup_env.sh' first}"

BISHENG="$ASCEND_HOME_PATH/bin/bisheng"
LD="$ASCEND_HOME_PATH/bin/ld.lld"

[ -x "$BISHENG" ] || { echo "[ERROR] bisheng not found at $BISHENG"; exit 1; }
[ -x "$LD" ]      || { echo "[ERROR] ld.lld   not found at $LD"; exit 1; }
[ -f "$KERNEL_SRC" ] || { echo "[ERROR] kernel source not found: $KERNEL_SRC"; exit 1; }

COMPILER_HELP=$("$BISHENG" --help)
if grep -q -- '--asc-aicore-lang' <<< "$COMPILER_HELP"; then
    LANGUAGE_FLAG=--asc-aicore-lang
elif grep -q -- '--cce-aicore-lang' <<< "$COMPILER_HELP"; then
    LANGUAGE_FLAG=--cce-aicore-lang
else
    echo "[ERROR] installed bisheng does not advertise an Ascend C language option"
    exit 1
fi

mkdir -p "$OUT_DIR"
OBJ="$OUT_DIR/${OP_NAME}_kernel.obj"
ELF="$OUT_DIR/${OP_NAME}_kernel.o"

echo "[INFO] Compiling $KERNEL_SRC -> $OBJ (npu-arch=$NPU_ARCH)"
"$BISHENG" -std=c++17 -fPIC --aicore-only "$ARCH_FLAG" -O2 \
    -I op_kernel -I op_host \
    -I "$ASCEND_HOME_PATH/include" \
    -I "$ASCEND_HOME_PATH/$(uname -m)-linux/include" \
    -I "$ASCEND_HOME_PATH/compiler/tikcpp/tikcfw" \
    -I "$ASCEND_HOME_PATH/compiler/tikcpp/tikcfw/impl" \
    -I "$ASCEND_HOME_PATH/compiler/tikcpp/tikcfw/interface" \
    "$LANGUAGE_FLAG" -c "$KERNEL_SRC" \
    -o "$OBJ"

echo "[INFO] Linking $OBJ -> $ELF"
"$LD" -m aicorelinux -Ttext=0 "$OBJ" -static -o "$ELF"

echo "[INFO] Done. File info:"
file "$ELF"
echo
echo "[INFO] Expected: ELF 64-bit LSB executable, *unknown arch 0x1029*, statically linked"
echo "[INFO] Tip: re-run with extra '-g' in BISHENG cmd for source-line hotspot in *_code_exe_*.csv"
