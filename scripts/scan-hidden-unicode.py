#!/usr/bin/env python3
"""Scan repository text files for dangerous hidden Unicode characters."""

from __future__ import annotations

import argparse
import os
import unicodedata
from pathlib import Path


ALLOWED_CONTROL_CODEPOINTS = {
    0x0009,  # tab
    0x000A,  # line feed
    0x000D,  # carriage return
}

DANGEROUS_CODEPOINTS = {
    0x00A0,
    0x200E,
    0x200F,
    0x2028,
    0x2029,
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
    "eval_reports",
    "exports",
    "minio-data",
    "node_modules",
    "out",
    "playwright-report",
    "postgres-data",
    "test-results",
    "venv",
}

SKIP_SUFFIXES = {
    ".avif",
    ".bmp",
    ".epub",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".svgz",
    ".webp",
    ".zip",
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
    suffix = path.suffix.lower()
    if suffix in SKIP_SUFFIXES:
        return False
    return path.name in TEXT_NAMES or suffix in TEXT_SUFFIXES


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


def is_suspicious(char: str) -> bool:
    codepoint = ord(char)
    category = unicodedata.category(char)
    if codepoint in ALLOWED_CONTROL_CODEPOINTS:
        return False
    if codepoint in DANGEROUS_CODEPOINTS:
        return True
    if 0x2000 <= codepoint <= 0x200A:
        return True
    if category == "Cf":
        return True
    if category == "Cc":
        return True
    if category in {"Zl", "Zp"}:
        return True
    if category == "Zs" and codepoint != 0x0020:
        return True
    return False


def printable_char(char: str, marker: str | None = None) -> str:
    codepoint = ord(char)
    if marker:
        return f"[{marker}]"
    if char == "\t":
        return "\\t"
    if char == "\n":
        return "\\n"
    if char == "\r":
        return "\\r"
    if is_suspicious(char):
        return f"[U+{codepoint:04X}]"
    return char


def visible_context(
    text: str,
    index: int,
    codepoint: str,
    radius: int = 32,
) -> str:
    line_start = text.rfind("\n", 0, index) + 1
    line_end = text.find("\n", index)
    if line_end == -1:
        line_end = len(text)
    start = max(line_start, index - radius)
    end = min(line_end, index + radius + 1)
    prefix = "..." if start > line_start else ""
    suffix = "..." if end < line_end else ""
    chars: list[str] = []
    for position in range(start, end):
        marker = codepoint if position == index else None
        chars.append(printable_char(text[position], marker))
    return f"{prefix}{''.join(chars)}{suffix}"


def scan_file(path: Path) -> list[tuple[int, int, str, str, str]]:
    data = path.read_bytes()
    if b"\x00" in data:
        return []
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return []
    findings: list[tuple[int, int, str, str, str]] = []
    for index, char in enumerate(text):
        if is_suspicious(char):
            codepoint = ord(char)
            line, column = line_column(text, index)
            name = unicodedata.name(char, "UNKNOWN")
            formatted_codepoint = f"U+{codepoint:04X}"
            findings.append(
                (
                    line,
                    column,
                    formatted_codepoint,
                    name,
                    visible_context(text, index, formatted_codepoint),
                )
            )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan text files for hidden or risky Unicode characters."
    )
    parser.add_argument("--root", default=".", help="Repository root to scan.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    findings: list[str] = []
    for path in sorted(iter_candidate_files(root)):
        if should_skip(path, root):
            continue
        for line, column, codepoint, name, context in scan_file(path):
            relative = path.relative_to(root)
            findings.append(
                f"{relative}:{line}:{column}: {codepoint} {name} | {context}"
            )

    if findings:
        print("Hidden Unicode findings:")
        for finding in findings:
            print(finding)
        return 1
    print("No dangerous hidden or risky Unicode characters found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
