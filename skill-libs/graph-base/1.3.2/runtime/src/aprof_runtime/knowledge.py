"""知识 API 与开发报告输出；编译身份由冻结的 v1 模块维持。"""
from pathlib import Path
import os
import re

from . import _knowledge_v1 as _compiler
from ._knowledge_v1 import *


def __getattr__(name):
    # 私有帮助函数也有既有调用者；编译器原字节不能随报告布局改变。
    return getattr(_compiler, name)


def build(root: Path, owner: str, *, report_dir: Path | None = None) -> dict:
    root = Path(root).resolve()
    report = root / REGIONS[owner] / "INITIALIZATION.md"
    if report.is_symlink():
        raise GraphError("初始化报告不能是符号链接")
    output = None
    if report_dir is not None:
        directory = Path(report_dir).resolve()
        if directory.is_relative_to(root):
            raise GraphError("开发报告目录必须位于技能包之外")
        output = directory / f"{owner}-INITIALIZATION.md"
        if output.exists() or output.is_symlink():
            raise GraphError("开发报告已存在，拒绝覆盖")
    if (root / "release.json").exists():
        raise GraphError("不能重建已发布包；先建立新的版本目录")
    previous = report.read_bytes() if report.is_file() else None
    completed = False
    try:
        artifact = _compiler.build(root, owner)
        completed = True
        if output is not None:
            body = report.read_text()
            def relocate(match):
                name = match[1]
                if re.match(r"\w+://", name) or name.startswith("#"):
                    return match[0]
                target = (report.parent / name).resolve()
                return match[0].replace(name, os.path.relpath(target, output.parent))
            body = re.sub(r"(?<!!)\[[^\]]*\]\(([^)]+)\)", relocate, body)
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("x", encoding="utf-8") as stream:
                stream.write(body + "\n")
        return artifact
    finally:
        if not completed and previous is not None:
            report.write_bytes(previous)
        else:
            report.unlink(missing_ok=True)
