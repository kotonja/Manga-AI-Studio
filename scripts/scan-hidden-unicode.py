#!/usr/bin/env python3
"""Scan repository text files for dangerous hidden Unicode format chars."""

from __future__ import annotations

import argparse
import os
import unicodedata
from pathlib import Path


DANGEROUS_CODEPOINTS = {
    0x200E,
    0x200F,
    0x202A,
    0x202B,
    0x202C,
    0x202D,
    0x202E,
    0x2066,
    0x2067,
    0x2068,
    0x2069,
    0xFEFF,
}

SKIP_DIRS = {
    ".git",
    ".next",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "coverage",
    "dist",
    "evidence",
    "minio-data",
    "node_modules",
    "out",
    "playwright-report",
    "postgres-data",
    "test-results",
    "venv",
}

TEXT_SUFFIXES = {
    ".cfg",
    ".css",
    ".env",
    ".example",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".ps1",
    ".py",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}

TEXT_NAMES = {
    ".dockerignore",
    ".env.example",
    ".env.prod.example",
    ".gitignore",
    "Dockerfile",
    "Makefile",
}


def is_candidate(path: Path) -> bool:
    return path.name in TEXT_NAMES or path.suffix.lower() in TEXT_SUFFIXES


def should_skip(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    return any(part in SKIP_DIRS for part in relative.parts)


def iter_candidate_files(root: Path):
    for directory_name, dirnames, filenames in os.walk(root):
        dirnames[:] = [dirname for dirname in dirnames if dirname not in SKIP_DIRS]
        directory = Path(directory_name)
        for filename in filenames:
            path = directory / filename
            if is_candidate(path):
                yield path


def line_column(text: str, index: int) -> tuple[int, int]:
    line = text.count("\n", 0, index) + 1
    last_newline = text.rfind("\n", 0, index)
    column = index + 1 if last_newline == -1 else index - last_newline
    return line, column


def scan_file(path: Path) -> list[tuple[int, int, str, str]]:
    data = path.read_bytes()
    if b"\x00" in data:
        return []
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return []
    findings: list[tuple[int, int, str, str]] = []
    for index, char in enumerate(text):
        codepoint = ord(char)
        category = unicodedata.category(char)
        if codepoint in DANGEROUS_CODEPOINTS or category == "Cf":
            line, column = line_column(text, index)
            name = unicodedata.name(char, "UNKNOWN")
            findings.append((line, column, f"U+{codepoint:04X}", name))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan text files for hidden/bidirectional Unicode format characters.")
    parser.add_argument("--root", default=".", help="Repository root to scan.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    findings: list[str] = []
    for path in sorted(iter_candidate_files(root)):
        if should_skip(path, root):
            continue
        for line, column, codepoint, name in scan_file(path):
            relative = path.relative_to(root)
            findings.append(f"{relative}:{line}:{column}: {codepoint} {name}")

    if findings:
        print("Hidden Unicode findings:")
        for finding in findings:
            print(finding)
        return 1
    print("No dangerous hidden Unicode format characters found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
