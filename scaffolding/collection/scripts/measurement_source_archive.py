"""Resolve frozen historical producer bytes without substituting experiment data.

Only read-only historical replay may use this resolver. New collection and its
admission always require the current, preregistered producer files directly.
"""
from pathlib import Path

from replay_timing_diagnosis import Evidence, digest, read, require

REPO = Path(__file__).resolve().parents[3]
SOURCE_ROOTS = (REPO / 'skill-libs/graph-base/0.5.1', REPO / 'scaffolding')


def source_archives(references):
    """Load explicitly hash-bound snapshots; workload/raw paths cannot be aliased."""
    files = {}
    for reference in references:
        require(set(reference) == {'path', 'sha256'}, 'invalid producer archive reference')
        path = Path(reference['path']).resolve(strict=True)
        require(digest(path) == reference['sha256'], 'producer archive index changed')
        index = read(path)
        require(index.get('schema_version') == 1 and index.get('not_a_release') is True,
                'producer archive is not a historical source snapshot')
        require(isinstance(index.get('files'), dict) and index['files'], 'empty producer archive')
        for original, item in index['files'].items():
            source = Path(original)
            require(source.is_absolute() and str(source.resolve(strict=False)) == original
                    and any(source.is_relative_to(root) for root in SOURCE_ROOTS),
                    'archive cannot substitute workload or experiment evidence')
            require(set(item) == {'path', 'sha256'} and Path(item['path']).is_absolute(),
                    'invalid archived source reference')
            key = (original, item['sha256'])
            # Separate studies may retain the very same producer in two places.
            files.setdefault(key, item)
    return files


class HistoricalEvidence(Evidence):
    """An expected historical hash selects its exact snapshot, never a new hash."""

    def __init__(self, archive_references, *, logical_paths=False):
        super().__init__()
        self.archive_references = archive_references
        self.archived = source_archives(archive_references)
        self.logical_paths = logical_paths
        self.logical_files = {}
        self.resolved_files = {}
        for reference in archive_references:
            super().bind(reference['path'], reference['sha256'])

    def bind(self, path, expected=None):
        key = str(Path(path).resolve(strict=False))
        if self.logical_paths and expected is None and key in self.logical_files:
            return dict(self.logical_files[key])
        archived = self.archived.get((key, expected))
        # Whole-package snapshots may also contain anchors and documents. Their
        # presence in an archive never permits replacing the original evidence.
        if not self._producer_path(Path(key)):
            archived = None
        if archived is not None:
            actual = super().bind(archived['path'], expected)
            self.resolved_files[key] = actual
        else:
            actual = super().bind(path, expected)
        logical = dict(actual, path=key)
        self.logical_files[key] = logical
        return logical if self.logical_paths else actual

    @staticmethod
    def _producer_path(path):
        package = REPO / 'skill-libs/graph-base/0.5.1'
        roots = (package / 'runtime/src', package / 'skills/ascendc-aprof-profiling/scripts',
                 package / 'skills/ascendc-aprof-profiling/assets',
                 REPO / 'scaffolding/collection/scripts', REPO / 'scaffolding/tools',
                 REPO / 'scaffolding/benchmarks/cannbench/harness')
        return path.suffix in {'.py', '.h', '.hpp'} and any(path.is_relative_to(root) for root in roots)

    def resolve_producer(self, original_path, expected_hash):
        """Resolve code only; raw data, config, receipts and anchors stay original."""
        path = Path(original_path).resolve(strict=False)
        require(self._producer_path(path), 'only registered producer code can use historical resolution')
        require((str(path), expected_hash) in self.archived, 'producer is absent from the frozen source archive')
        self.bind(path, expected_hash)
        return Path(self.archived[(str(path), expected_hash)]['path'])

    def semantic_files(self):
        """Original paths reproduce an old result; resolved_files audits new reads."""
        return {path: item['sha256'] for path, item in self.logical_files.items()}
