#!/usr/bin/env python3
"""Package and documentation validator for adhd-coding-skill.

Checks:
1. UTF-8 decoding (no BOM), LF line endings, and trailing newline on tracked text files.
2. SKILL.md YAML frontmatter fields (name, description) and non-empty body.
3. agents/openai.yaml interface fields and $adhd-coding prompt reference.
4. Local relative Markdown links across all Markdown files.
5. Scenario coverage: S1-S10 present in tests/scenarios.md table and tests/live_eval.py.
6. Python compilation of tests/*.py.
7. Git whitespace check (`git diff --check`).
"""

from __future__ import annotations

import pathlib
import py_compile
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILL_MD = ROOT / "skills" / "adhd-coding" / "SKILL.md"
OPENAI_YAML = ROOT / "skills" / "adhd-coding" / "agents" / "openai.yaml"
LIVE_EVAL_PY = ROOT / "tests" / "live_eval.py"
SCENARIOS_MD = ROOT / "tests" / "scenarios.md"
EXPECTED_SCENARIOS = [f"S{i}" for i in range(1, 11)]
MARKDOWN_FILES = [
    ROOT / "README.md",
    ROOT / "README.tr.md",
    SKILL_MD,
    ROOT / "tests" / "scenarios.md",
    ROOT / "tests" / "evaluation.md",
]


def check_frontmatter(path: pathlib.Path, errors: list[str]) -> None:
    if not path.is_file():
        errors.append(f"Missing skill file: {path}")
        return
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        errors.append(f"{path}: missing opening YAML frontmatter delimiter '---'")
        return
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        errors.append(f"{path}: missing closing YAML frontmatter delimiter '---'")
        return
    frontmatter, body = parts[0][4:], parts[1]
    meta: dict[str, str] = {}
    for line in frontmatter.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"').strip("'")
    if meta.get("name") != "adhd-coding":
        errors.append(f"{path}: expected frontmatter name 'adhd-coding', got {meta.get('name')!r}")
    desc = meta.get("description", "")
    if len(desc) < 40:
        errors.append(f"{path}: frontmatter description is too short ({len(desc)} chars)")
    if len(body.strip()) < 200:
        errors.append(f"{path}: skill body is unexpectedly short ({len(body.strip())} chars)")


def check_openai_yaml(path: pathlib.Path, errors: list[str]) -> None:
    if not path.is_file():
        errors.append(f"Missing Codex metadata file: {path}")
        return
    text = path.read_text(encoding="utf-8")
    for key in ("display_name:", "short_description:", "default_prompt:"):
        if key not in text:
            errors.append(f"{path}: missing key {key}")
    if "$adhd-coding" not in text:
        errors.append(f"{path}: default_prompt should reference '$adhd-coding'")


def check_markdown_links(md_files: list[pathlib.Path], errors: list[str]) -> None:
    link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for md in md_files:
        if not md.is_file():
            errors.append(f"Missing Markdown file: {md}")
            continue
        text = md.read_text(encoding="utf-8")
        for match in link_pattern.finditer(text):
            target = match.group(1).strip()
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target_path = target.split("#", 1)[0]
            resolved = (md.parent / target_path).resolve()
            if not resolved.exists():
                errors.append(f"{md.relative_to(ROOT)}: broken local link '{target}' -> {resolved}")


def check_text_hygiene(errors: list[str]) -> None:
    paths = [*(p for p in MARKDOWN_FILES), OPENAI_YAML, LIVE_EVAL_PY, pathlib.Path(__file__)]
    for path in paths:
        if not path.is_file():
            errors.append(f"Missing tracked file: {path}")
            continue
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            errors.append(f"{path.relative_to(ROOT)}: not valid UTF-8")
            continue
        if text.startswith("\ufeff"):
            errors.append(f"{path.relative_to(ROOT)}: starts with UTF-8 BOM")
        if "\r" in text:
            errors.append(f"{path.relative_to(ROOT)}: contains CR line endings; use LF")
        if not text.endswith("\n"):
            errors.append(f"{path.relative_to(ROOT)}: missing trailing newline")


def check_scenario_coverage(errors: list[str]) -> None:
    if not SCENARIOS_MD.is_file():
        errors.append(f"Missing scenario file: {SCENARIOS_MD}")
    else:
        table = SCENARIOS_MD.read_text(encoding="utf-8")
        for sid in EXPECTED_SCENARIOS:
            if f"| {sid} |" not in table:
                errors.append(f"tests/scenarios.md: missing table row for {sid}")
    if not LIVE_EVAL_PY.is_file():
        errors.append(f"Missing live runner: {LIVE_EVAL_PY}")
    else:
        runner = LIVE_EVAL_PY.read_text(encoding="utf-8")
        for sid in EXPECTED_SCENARIOS:
            if f'"{sid}"' not in runner:
                errors.append(f"tests/live_eval.py: missing scenario {sid}")


def check_python_compile(errors: list[str]) -> None:
    for script in (pathlib.Path(__file__), LIVE_EVAL_PY):
        try:
            py_compile.compile(str(script), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"{script.relative_to(ROOT)}: compile failed: {exc}")


def check_git_whitespace(errors: list[str]) -> None:
    proc = subprocess.run(
        ["git", "diff", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0 or proc.stdout.strip():
        errors.append(f"git diff --check reported whitespace issues:\n{proc.stdout.strip()}")


def main() -> int:
    errors: list[str] = []
    check_frontmatter(SKILL_MD, errors)
    check_openai_yaml(OPENAI_YAML, errors)
    check_markdown_links(MARKDOWN_FILES, errors)
    check_text_hygiene(errors)
    check_scenario_coverage(errors)
    check_python_compile(errors)
    check_git_whitespace(errors)

    if errors:
        print("Package validation FAILED:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("Skill is valid! All package, metadata, link, coverage, hygiene, and whitespace checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
