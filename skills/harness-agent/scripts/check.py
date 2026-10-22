#!/usr/bin/env python3
"""只读检查基础文件、OKF 元数据和 Markdown 行内文件链接。"""

import argparse
import datetime
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

try:
    import yaml
except ImportError:
    print(json.dumps({"passed": False, "errors": ["缺少 PyYAML；使用已有环境或报告未验证"]}, ensure_ascii=False))
    sys.exit(2)


TEMPLATES = Path(__file__).resolve().parents[1] / "templates"
REQUIRED = tuple(
    path.relative_to(TEMPLATES).as_posix()
    for path in sorted(TEMPLATES.rglob("*")) if path.is_file()
)
SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__"}


def metadata(text, label, errors):
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", text, re.S)
    if not match:
        errors.append(f"{label}: 缺少 YAML 元数据块")
        return {}
    try:
        result = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        errors.append(f"{label}: YAML 元数据无法解析")
        return {}
    if not isinstance(result, dict):
        errors.append(f"{label}: 元数据须为映射")
        return {}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path, help="目标仓库目录")
    args = parser.parse_args()
    repo = args.repo.absolute()
    bundle = repo / "harness"
    errors = []
    warnings = []
    if not REQUIRED:
        print(json.dumps({"passed": False, "errors": ["模板目录为空或缺失"]}, ensure_ascii=False))
        return 1
    if not repo.is_dir() or repo.is_symlink() or not bundle.is_dir() or bundle.is_symlink():
        print(json.dumps({"passed": False, "errors": ["仓库与 harness 须为已有普通目录"]}, ensure_ascii=False))
        return 1

    for relative in ("AGENTS.md", *("harness/" + p for p in REQUIRED)):
        target = repo / relative
        if target.is_symlink() or any(p.is_symlink() for p in target.parents if p != repo and repo in p.parents):
            errors.append(f"{relative}: 保留符号链接，未读取")
        elif not target.is_file():
            errors.append(f"{relative}: 缺少必需文件")

    files = []
    root_agents = repo / "AGENTS.md"
    if root_agents.is_file() and not root_agents.is_symlink():
        files.append(root_agents)
    for directory, dirs, names in os.walk(bundle, followlinks=False):
        for name in list(dirs):
            target = Path(directory) / name
            if name in SKIP_DIRS:
                dirs.remove(name)
            elif target.is_symlink():
                errors.append(f"{target.relative_to(repo)}: 保留符号链接目录，未读取")
                dirs.remove(name)
        for name in sorted(names):
            target = Path(directory) / name
            if target.suffix == ".md":
                if target.is_symlink() or not target.is_file():
                    errors.append(f"{target.relative_to(repo)}: 保留非普通 Markdown 文件，未读取")
                else:
                    files.append(target)

    for path in sorted(files):
        label = path.relative_to(repo).as_posix()
        text = path.read_text(encoding="utf-8")
        if path != root_agents:
            if path.name == "index.md":
                if path == bundle / "index.md":
                    data = metadata(text, label, errors)
                    if data.get("okf_version") != "0.2":
                        errors.append(f"{label}: 须声明 okf_version 字符串 0.2")
                elif text.startswith("---\n") or text.startswith("---\r\n"):
                    errors.append(f"{label}: 子目录索引禁止使用元数据块")
            elif path.name == "log.md":
                if text.startswith("---\n") or text.startswith("---\r\n"):
                    errors.append(f"{label}: 日志禁止使用元数据块")
                for date in re.findall(r"^##\s+(.+?)\s*$", text, re.M):
                    try:
                        datetime.date.fromisoformat(date)
                        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
                            raise ValueError
                    except ValueError:
                        errors.append(f"{label}: 日期标题须为 YYYY-MM-DD")
            else:
                data = metadata(text, label, errors)
                for key in ("type", "title", "status"):
                    if not isinstance(data.get(key), str) or not data[key].strip():
                        errors.append(f"{label}: {key} 须为非空字符串")

        # 跳过围栏代码与行内代码；不解析引用式链接和标题锚点。
        prose = re.sub(r"(?ms)^\s*(`{3,}|~{3,})[^\n]*\n.*?^\s*\1\s*$", "", text)
        prose = re.sub(r"`[^`\n]*`", "", prose)
        for href in re.findall(r"\[[^\]\n]*\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)", prose):
            href = href.strip("<>")
            parts = urlsplit(href)
            if parts.scheme or parts.netloc or not parts.path:
                continue
            target_path = unquote(parts.path)
            base = repo if path == root_agents else bundle
            target = base / target_path.lstrip("/") if target_path.startswith("/") else path.parent / target_path
            if not target.exists():
                errors.append(f"{label}: 本地文件链接缺失 {href}")

    print(json.dumps({
        "repo": str(repo), "passed": not errors, "checked_files": len(files),
        "errors": errors, "warnings": warnings,
        "excluded_directories": sorted(SKIP_DIRS),
        "limits": ["不检查授权与规则语义", "不检查引用式链接、标题锚点或外部 URL", "不验证全部可选 OKF 元数据"],
    }, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, UnicodeError, ValueError) as error:
        print(json.dumps({"passed": False, "errors": [str(error)]}, ensure_ascii=False))
        sys.exit(1)
