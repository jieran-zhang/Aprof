"""归档完整性与包边界；不运行硬件或重写历史记录。"""
import hashlib
import json
from pathlib import Path
import re


ARCHIVE = Path(__file__).resolve().parents[1]
REPOSITORY = ARCHIVE.parents[2]
PACKAGE = REPOSITORY / 'skill-libs/graph-base/1.3.1'
PREVIOUS = PACKAGE.with_name('1.3.0')


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def test_archive_preserves_payloads_and_runtime_sources():
    manifest = json.loads((ARCHIVE / 'relocation.json').read_text())
    assert len(manifest['groups']) == 7
    for name, count in manifest['groups'].items():
        assert not (PACKAGE / 'workflows/references' / name).exists()
        assert sum(p.is_file() for p in (ARCHIVE / name).rglob('*')) == count
    for entry in manifest['files']:
        original = PREVIOUS / entry['original_path']
        relocated = ARCHIVE / entry['path']
        assert sha(original) == entry['original_sha256'], original
        assert sha(relocated) == entry['sha256'], relocated
        assert relocated.stat().st_size == entry['bytes']
        if entry['sha256'] != entry['original_sha256']:
            assert entry['path'] in manifest['edited_documents'] or entry['path'].startswith('tools/')
    for source in (PREVIOUS / 'runtime/src').rglob('*.py'):
        assert sha(PACKAGE / source.relative_to(PREVIOUS)) == sha(source)
    for name in ('knowledge-history', 'action-routing-snapshots', 'action-condition-policies'):
        previous = PREVIOUS / 'workflows/references' / name
        for source in previous.rglob('*'):
            if source.is_file():
                assert sha(PACKAGE / source.relative_to(PREVIOUS)) == sha(source)
    registry = json.loads((PACKAGE / 'skills/registry.json').read_text())
    assert registry['library']['version'] == registry['workflow_plugin']['version'] == '1.3.1'
    for host in ('.codex-plugin', '.claude-plugin'):
        assert json.loads((PACKAGE / host / 'plugin.json').read_text())['version'] == '1.3.1'


def test_relocated_navigation_resolves_without_package_external_links():
    for root in (PACKAGE, ARCHIVE):
        for path in root.rglob('*.md'):
            parts = path.relative_to(root).parts
            if any(part in {'sources', 'history', 'knowledge-history', 'archive', 'seed-v0003'}
                   or part.startswith('review-before-') for part in parts):
                continue
            if root == ARCHIVE and 'answers' in parts:
                continue  # 模型原始回答是带 hash 的实验记录，链接仍反映当时目录。
            body = re.sub(r'```.*?```', '', path.read_text(), flags=re.S)
            for link in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)', body):
                link = link.split('#')[0].strip('<>')
                if not link or re.match(r'\w+://', link) or link.startswith('mailto:'):
                    continue
                target = (path.parent / link).resolve()
                assert target.exists(), f'{path}: {link}'
                boundary = PACKAGE if root == PACKAGE else REPOSITORY
                assert target.is_relative_to(boundary), f'{path}: {link}'
