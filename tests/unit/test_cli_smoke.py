from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout

from aprof.cli.main import main


class CliSmokeTests(unittest.TestCase):
    def test_skills_command(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["skills"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertGreaterEqual(len(payload), 5)
        self.assertEqual(payload[0]["name"], "collect_operator_timeline")


if __name__ == "__main__":
    unittest.main()
