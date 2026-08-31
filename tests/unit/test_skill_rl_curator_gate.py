import tempfile
import unittest
from pathlib import Path

from aprof.skill_rl.curator import filter_executable_edits, propose_edits
from aprof.skill_rl.episode_adapter import adapt_fixture_a, adapt_fixture_b
from aprof.skill_rl.library import SkillLibrary
from aprof.skill_rl.models import SkillEdit
from aprof.skill_rl.validation_gate import validate_edits


class TestSkillRlCuratorGate(unittest.TestCase):
    def setUp(self):
        self.repo_lib = SkillLibrary(version_label="v0")
        self.repo_lib.load()

    def test_failure_is_delete_or_merged_contraindication(self):
        ep = adapt_fixture_b()
        edits = propose_edits(ep, self.repo_lib.skills)
        deps = [e for e in edits if e.op == "DELETE"]
        merged = [
            e
            for e in edits
            if e.op in ("ADD", "UPDATE") and e.payload.get("contraindications")
        ]
        self.assertTrue(deps or merged)

    def test_filter_rejects_empty_actionable(self):
        bad = SkillEdit(
            op="UPDATE",
            skill_id="tiling.increase_blockdim_when_underused",
            payload={"notes": "be faster somehow"},
            scope="production_safe",
        )
        self.assertEqual(filter_executable_edits([bad]), [])

    def test_gate_accepts_curation_and_can_commit(self):
        train = adapt_fixture_a()
        dev = adapt_fixture_b()
        edits = filter_executable_edits(propose_edits(train, self.repo_lib.skills))
        ok, applied, report = validate_edits(edits, base_library=self.repo_lib, dev_episodes=[dev, train])
        self.assertTrue(ok, msg=str(report))
        self.assertTrue(applied)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # Copy v0 into temp by loading then committing via trial path
            lib = SkillLibrary(root=root, version_label="v0")
            lib.skills = dict(self.repo_lib.skills)
            lib.commit("v0")
            lib2 = SkillLibrary(root=root, version_label="v0")
            lib2.load()
            ok2, applied2, _ = validate_edits(edits, base_library=lib2, dev_episodes=[train])
            self.assertTrue(ok2)
            trial = SkillLibrary(root=root, version_label="v0")
            trial.skills = dict(lib2.skills)
            trial.apply_edits(applied2)
            snap = trial.commit("v1")
            self.assertEqual(snap.version_label, "v1")
            self.assertTrue(snap.content_hash)
            self.assertTrue((root / "v1" / "manifest.json").exists())

    def test_gate_rejects_non_actionable_overwrite(self):
        lib = SkillLibrary(version_label="v0")
        lib.load()
        toxic = [
            SkillEdit(
                op="UPDATE",
                skill_id="tiling.increase_blockdim_when_underused",
                payload={
                    "id": "tiling.increase_blockdim_when_underused",
                    "family": "tiling",
                    "actionable_edits": [],
                    "expected_metric_delta": {},
                },
                scope="production_safe",
            )
        ]
        # filter removes it before gate
        self.assertEqual(filter_executable_edits(toxic), [])


if __name__ == "__main__":
    unittest.main()
