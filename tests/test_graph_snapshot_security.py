from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from aprof_runtime.errors import GraphError
from aprof_runtime.graph import load_snapshot


REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = REPO_ROOT / "skillgraph" / "versions" / "v0001"


class GraphSnapshotPathSecurityTest(unittest.TestCase):
    def _copy_snapshot(self, root: Path) -> Path:
        target = root / "snapshot"
        shutil.copytree(SNAPSHOT, target)
        return target

    def test_manifest_paths_must_stay_inside_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = self._copy_snapshot(root)
            manifest_path = snapshot / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["lineage"] = "../outside.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(GraphError, "normalized snapshot-relative"):
                load_snapshot(snapshot)

    def test_checksum_paths_must_stay_inside_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = self._copy_snapshot(root)
            checksums_path = snapshot / "checksums.json"
            checksums = json.loads(checksums_path.read_text(encoding="utf-8"))
            checksums["files"]["../outside.json"] = "0" * 64
            checksums_path.write_text(json.dumps(checksums), encoding="utf-8")
            with self.assertRaisesRegex(GraphError, "normalized snapshot-relative"):
                load_snapshot(snapshot)

    def test_snapshot_symlink_cannot_redirect_manifest_file_outside(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = self._copy_snapshot(root)
            outside = root / "outside"
            outside.mkdir()
            shutil.copy2(snapshot / "lineage.json", outside / "lineage.json")
            (snapshot / "redirect").symlink_to(outside, target_is_directory=True)
            manifest_path = snapshot / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["lineage"] = "redirect/lineage.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(GraphError, "outside snapshot root"):
                load_snapshot(snapshot)

    def test_snapshot_manifest_itself_cannot_be_an_external_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = self._copy_snapshot(root)
            outside_manifest = root / "outside-manifest.json"
            shutil.copy2(snapshot / "manifest.json", outside_manifest)
            (snapshot / "manifest.json").unlink()
            (snapshot / "manifest.json").symlink_to(outside_manifest)
            with self.assertRaisesRegex(GraphError, "outside snapshot root"):
                load_snapshot(snapshot)


if __name__ == "__main__":
    unittest.main()
