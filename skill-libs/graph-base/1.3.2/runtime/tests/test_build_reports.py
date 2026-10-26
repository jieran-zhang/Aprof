"""报告输出不改变冻结编译身份，也不向技能目录重新填入开发材料。"""
from pathlib import Path
import shutil

import pytest

from aprof_runtime.errors import GraphError
from aprof_runtime.knowledge import REGIONS, build, verify


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def package(tmp_path_factory):
    root = tmp_path_factory.mktemp('build-report-package') / 'package'
    shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    return root


def test_default_build_preserves_identity_without_initialization_report(package):
    for owner in ('parallel-planning', 'optimization'):
        before = verify(package, owner)
        assert build(package, owner) == before == verify(package, owner)
    assert not list(package.rglob('INITIALIZATION.md'))


def test_external_report_and_overwrite_boundary(package, tmp_path):
    owner = 'parallel-planning'
    expected = verify(package, owner)
    reports = tmp_path / 'reports'
    assert build(package, owner, report_dir=reports) == expected
    report = reports / (owner + '-INITIALIZATION.md')
    assert 'planning.' in report.read_text()
    assert not (package / REGIONS[owner] / 'INITIALIZATION.md').exists()
    before = report.read_bytes()
    with pytest.raises(GraphError, match='拒绝覆盖'):
        build(package, owner, report_dir=reports)
    assert report.read_bytes() == before


def test_report_cannot_be_written_inside_package(package):
    with pytest.raises(GraphError, match='技能包之外'):
        build(package, 'optimization', report_dir=package / 'generated')
    assert not (package / 'generated').exists()


def test_generated_report_cannot_follow_an_existing_symlink(package, tmp_path):
    target = tmp_path / 'keep.txt'
    target.write_text('keep')
    report = package / REGIONS['parallel-planning'] / 'INITIALIZATION.md'
    report.symlink_to(target)
    try:
        with pytest.raises(GraphError, match='符号链接'):
            build(package, 'parallel-planning')
        assert target.read_text() == 'keep'
    finally:
        report.unlink()
