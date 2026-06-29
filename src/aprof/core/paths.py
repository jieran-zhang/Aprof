from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def configs_dir() -> Path:
    return repo_root() / "configs"


def architectures_dir() -> Path:
    return configs_dir() / "architectures"


def benchmarks_dir() -> Path:
    return repo_root() / "benchmarks"


def skills_dir() -> Path:
    return repo_root() / "skills"


def default_architecture_path() -> Path:
    return architectures_dir() / "ascend910b1.yaml"
