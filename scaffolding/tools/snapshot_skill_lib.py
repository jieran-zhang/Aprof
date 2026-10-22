#!/usr/bin/env python3
"""调用所选包自己的校验器，将完整字节冻结到一个全新的归档根。"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import shutil

from validate_learning_records import file_hash


def snapshot(source: Path, output: Path):
    source, output = source.resolve(strict=True), output.resolve()
    if output.is_relative_to(source) or output.exists():
        raise ValueError("输出必须是包外尚不存在的新目录")
    spec = importlib.util.spec_from_file_location("selected_release", source / "tools/release.py")
    release = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(release)
    sealed = (source / "release.json").is_file()
    manifest = release.verify(source) if sealed else release.verify_unsealed(source)
    if manifest["release_id"] == "graph-base/1.2.0" and not output.is_relative_to("/dev/shm"):
        raise ValueError("1.2.0 runtime snapshots must remain under /dev/shm; source delivery is separate")
    files = dict(manifest["files"])
    if sealed:
        files["release.json"] = file_hash(source / "release.json")
    output.mkdir(parents=True, exist_ok=False)
    copied = {}
    for name, expected in sorted(files.items()):
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"包内路径越界: {name}")
        original = source / relative
        if original.is_symlink() or not original.resolve().is_relative_to(source):
            raise ValueError(f"包内源文件越界或为 symlink: {name}")
        target = output / "skill-lib" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, target)
        if file_hash(target) != expected:
            raise ValueError(f"复制期间源文件改变: {name}")
        copied[target.relative_to(output).as_posix()] = expected
    snapshot_manifest = {
        "schema_version": "aprof.skill-lib-snapshot/v1",
        "release_id": manifest["release_id"], "runtime_version": manifest["runtime_version"],
        "source_status": manifest["status"], "source_path": str(source), "files": copied,
        "publication_performed": False,
    }
    # 清单最后落盘；中断留下的目录没有完整快照资格，不覆盖或清理已有材料。
    path = output / "skill-lib.snapshot.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(snapshot_manifest, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    return {"skill_lib_ref": {"path": path.name, "sha256": file_hash(path)}, "files": len(copied)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-lib", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(snapshot(args.skill_lib, args.output), ensure_ascii=False))
    except (ValueError, OSError) as error:
        parser.exit(1, f"冻结失败: {error}\n")


if __name__ == "__main__":
    main()
