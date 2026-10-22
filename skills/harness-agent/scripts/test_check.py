"""通过 CLI 验证必需文件、元数据和文件保护。"""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SKILL = Path(__file__).resolve().parents[1]


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        shutil.copytree(SKILL / "templates", self.repo / "harness")
        (self.repo / "AGENTS.md").write_text(
            "[工作规则](harness/AGENTS.md)\n", encoding="utf-8")

    def check(self, *args):
        result = subprocess.run(
            [sys.executable, str(SKILL / "scripts/check.py"),
             "--repo", str(self.repo), *args], capture_output=True, text=True)
        data = json.loads(result.stdout)
        self.assertEqual(result.returncode == 0, data["passed"])
        return result.returncode, data

    def test_fresh_templates(self):
        code, data = self.check()
        self.assertEqual(code, 0, data)

    def test_required_metadata_rejects_missing_empty_and_wrong_types(self):
        path = self.repo / "harness/architecture.md"
        for key in ("type", "title", "status"):
            for value in (None, "", "  ", 12, [], False):
                with self.subTest(key=key, value=value):
                    data = {"type": "Architecture", "title": "架构", "status": "draft"}
                    if value is None:
                        del data[key]
                    else:
                        data[key] = value
                    path.write_text("---\n" + json.dumps(data) + "\n---\n", encoding="utf-8")
                    code, result = self.check()
                    self.assertEqual(code, 1, result)
                    self.assertTrue(any(key in error for error in result["errors"]))

    def test_missing_required_file_fails(self):
        (self.repo / "harness/principles/AGENTS.md").unlink()
        code, data = self.check()
        self.assertEqual(code, 1)
        self.assertTrue(any("principles/AGENTS.md" in error for error in data["errors"]))

    def test_symlink_target_is_rejected(self):
        path = self.repo / "harness/architecture.md"
        outside = self.repo / "outside.md"
        path.rename(outside)
        original = outside.read_bytes()
        path.symlink_to(outside)
        self.assertEqual(self.check()[0], 1)
        self.assertEqual(outside.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
