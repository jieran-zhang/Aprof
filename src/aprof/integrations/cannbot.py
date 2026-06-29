from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aprof.core.errors import AProfError
from aprof.core.paths import repo_root, skills_dir


class CannbotSkillsError(AProfError):
    """Raised when the CANNBot skills submodule is missing or invalid."""


@dataclass(frozen=True)
class CannbotSkill:
    name: str
    path: Path
    skill_md: Path
    category: str


def cannbot_skills_root() -> Path:
    root = repo_root() / "third_party" / "cannbot-skills"
    if not root.exists():
        raise CannbotSkillsError(
            "CANNBot skills not found. Run: git submodule update --init --recursive"
        )
    return root.resolve()


def aprof_skills_root() -> Path:
    return (skills_dir() / "aprof").resolve()


def _skill_categories() -> list[tuple[str, Path]]:
    root = cannbot_skills_root()
    return [
        ("ops", root / "ops"),
        ("graph", root / "graph"),
        ("model", root / "model"),
        ("infra", root / "infra"),
        ("ops-lab", root / "ops-lab"),
    ]


def list_skill_dirs() -> list[Path]:
    """Return all CANNBot skill directories that contain SKILL.md."""

    dirs: list[Path] = []
    for _, base in _skill_categories():
        if not base.exists():
            continue
        for path in sorted(base.iterdir()):
            if path.is_dir() and (path / "SKILL.md").exists():
                dirs.append(path)
    return dirs


def list_skills() -> list[CannbotSkill]:
    skills: list[CannbotSkill] = []
    for category, base in _skill_categories():
        if not base.exists():
            continue
        for path in sorted(base.iterdir()):
            skill_md = path / "SKILL.md"
            if path.is_dir() and skill_md.exists():
                skills.append(
                    CannbotSkill(
                        name=path.name,
                        path=path.resolve(),
                        skill_md=skill_md.resolve(),
                        category=category,
                    )
                )
    return skills


def get_skill_dir(name: str) -> Path:
    return resolve_skill(name).path


def get_skill_markdown(name: str) -> str:
    skill = resolve_skill(name)
    return skill.skill_md.read_text(encoding="utf-8")


def resolve_skill(name: str) -> CannbotSkill:
    for skill in list_skills():
        if skill.name == name:
            return skill
    raise CannbotSkillsError(f"CANNBot skill not found: {name}")
