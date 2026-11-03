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
        (self.repo / "harness").mkdir()
        for name in ("AGENTS.md", "index.md"):
            shutil.copyfile(SKILL / "templates" / name, self.repo / "harness" / name)
        (self.repo / "AGENTS.md").write_text(
            "[工作规则](harness/AGENTS.md)\n", encoding="utf-8")

    def check(self, *args):
        result = subprocess.run(
            [sys.executable, str(SKILL / "scripts/check.py"),
             "--repo", str(self.repo), *args], capture_output=True, text=True)
        data = json.loads(result.stdout)
        self.assertEqual(result.returncode == 0, data["passed"])
        return result.returncode, data

    def test_minimal_set_without_optional_templates(self):
        code, data = self.check()
        self.assertEqual(code, 0, data)

    def test_custom_flat_and_nested_layouts(self):
        for name in ("boundaries.md", "design/runtime/contract.md"):
            p = self.repo / "harness" / name
            p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SKILL / "templates/architecture.md", p)
        index = self.repo / "harness/index.md"
        index.write_text(index.read_text() + "\n[边界](boundaries.md)\n[合同](design/runtime/contract.md)\n")
        before = {p.relative_to(self.repo): p.read_bytes()
                  for p in self.repo.rglob("*") if p.is_file()}
        self.assertEqual(self.check()[0], 0)
        after = {p.relative_to(self.repo): p.read_bytes()
                 for p in self.repo.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_broken_optional_document_link_fails(self):
        index = self.repo / "harness/index.md"
        index.write_text(index.read_text() + "\n[缺失合同](design/missing.md)\n")
        code, data = self.check()
        self.assertEqual(code, 1)
        self.assertTrue(any("design/missing.md" in e for e in data["errors"]))

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
        (self.repo / "harness/AGENTS.md").unlink()
        code, data = self.check()
        self.assertEqual(code, 1)
        self.assertTrue(any("harness/AGENTS.md" in error for error in data["errors"]))

    def test_symlink_target_is_rejected(self):
        path = self.repo / "harness/architecture.md"
        outside = self.repo / "outside.md"
        shutil.copyfile(SKILL / "templates/architecture.md", outside)
        original = outside.read_bytes()
        path.symlink_to(outside)
        self.assertEqual(self.check()[0], 1)
        self.assertEqual(outside.read_bytes(), original)

    def test_external_document_does_not_require_local_template(self):
        docs = self.repo / "docs"
        docs.mkdir()
        shutil.copyfile(SKILL / "templates/architecture.md", docs / "architecture.md")
        index = self.repo / "harness/index.md"
        index.write_text(index.read_text().replace(
            "(AGENTS.md)", "(../docs/architecture.md)"), encoding="utf-8")
        code, data = self.check()
        self.assertEqual(code, 0, data)

    def test_external_document_content_is_out_of_scope(self):
        docs = self.repo / "docs"
        docs.mkdir()
        outside = docs / "architecture.md"
        outside.write_text("[失效链接](missing.md)\n", encoding="utf-8")
        original = outside.read_bytes()
        index = self.repo / "harness/index.md"
        index.write_text(index.read_text() + "\n[外部参考](../docs/architecture.md)\n",
                         encoding="utf-8")
        code, data = self.check()
        self.assertEqual(code, 0, data)
        self.assertEqual(outside.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
