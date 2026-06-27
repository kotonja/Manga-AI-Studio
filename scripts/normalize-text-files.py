#!/usr/bin/env python3
"""Report and normalize tracked text files for LF-only source control.

The implementation intentionally works from bytes first so collapsed line
endings, UTF-8 BOMs, and invisible Unicode are visible before Python text
decoding can hide them.
The normalizer is intentionally stored as real LF-delimited text in Git.
Raw GitHub byte checks should show this as normal multiline Python.
"""

from __future__ import annotations

import argparse
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path


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
    ".gitattributes",
    ".gitignore",
    "Dockerfile",
    "Makefile",
}

BINARY_SUFFIXES = {
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

CRITICAL_LF_MINIMUMS = {
    ".gitattributes": 20,
    "scripts/check-alpha-env.py": 150,
    "scripts/create-alpha-token.py": 40,
    "scripts/alpha-smoke-test.py": 100,
    "scripts/scan-hidden-unicode.py": 150,
    "scripts/normalize-text-files.py": 150,
    "services/api/manga_api/routes/alpha.py": 150,
}

SKIP_PARTS = {
    ".git",
    ".next",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "coverage",
    "dist",
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

ALLOWED_CONTROL_CODEPOINTS = {
    0x0009,  # tab
    0x000A,  # line feed
}


@dataclass
class UnicodeFinding:
    index: int
    codepoint: int
    name: str


@dataclass
class FileReport:
    path: Path
    lf_count: int
    cr_count: int
    crlf_count: int
    lone_cr_count: int
    ends_with_newline: bool
    has_bom: bool
    unicode_findings: list[UnicodeFinding]
    collapsed_multiline: bool
    decode_error: str | None
    would_change: bool

    @property
    def has_suspicious_unicode(self) -> bool:
        return self.has_bom or bool(self.unicode_findings) or self.decode_error is not None

    @property
    def has_line_ending_issue(self) -> bool:
        return self.cr_count > 0

    @property
    def is_clean(self) -> bool:
        return (
            not self.has_line_ending_issue
            and self.ends_with_newline
            and not self.collapsed_multiline
            and not self.has_suspicious_unicode
        )


def repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip()).resolve()


def tracked_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
        cwd=root,
    )
    names = result.stdout.decode("utf-8").split("\0")
    return [root / name for name in names if name]


def is_text_candidate(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    if any(part in SKIP_PARTS for part in relative.parts):
        return False
    suffix = path.suffix.lower()
    if suffix in BINARY_SUFFIXES:
        return False
    return path.name in TEXT_NAMES or suffix in TEXT_SUFFIXES


def is_suspicious_char(char: str) -> bool:
    codepoint = ord(char)
    category = unicodedata.category(char)
    if codepoint in ALLOWED_CONTROL_CODEPOINTS:
        return False
    if codepoint == 0x00A0:
        return True
    if 0x2000 <= codepoint <= 0x200A:
        return True
    if codepoint in {0x2028, 0x2029, 0xFEFF}:
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


def normalize_text(data: bytes) -> bytes:
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    text = data.decode("utf-8")
    normalized: list[str] = []
    for char in text:
        codepoint = ord(char)
        category = unicodedata.category(char)
        if char in {"\n", "\t"}:
            normalized.append(char)
        elif codepoint == 0x00A0 or 0x2000 <= codepoint <= 0x200A:
            normalized.append(" ")
        elif category == "Zs" and codepoint != 0x0020:
            normalized.append(" ")
        elif category in {"Zl", "Zp"}:
            normalized.append("\n")
        elif category == "Cf":
            continue
        elif category == "Cc":
            normalized.append(" ")
        else:
            normalized.append(char)
    return ("".join(normalized).rstrip("\n") + "\n").encode("utf-8")


def critical_lf_minimum(path: Path) -> int | None:
    normalized = path.as_posix()
    for suffix, minimum in CRITICAL_LF_MINIMUMS.items():
        if normalized.endswith(suffix):
            return minimum
    return None


def analyze_file(path: Path) -> FileReport:
    data = path.read_bytes()
    lf_count = data.count(b"\n")
    cr_count = data.count(b"\r")
    crlf_count = data.count(b"\r\n")
    lone_cr_count = cr_count - crlf_count
    ends_with_newline = data.endswith(b"\n")
    has_bom = data.startswith(b"\xef\xbb\xbf")
    minimum_lf = critical_lf_minimum(path)
    collapsed_multiline = minimum_lf is not None and lf_count < minimum_lf
    decode_error: str | None = None
    unicode_findings: list[UnicodeFinding] = []

    try:
        text = data.decode("utf-8")
        for index, char in enumerate(text):
            if is_suspicious_char(char):
                unicode_findings.append(
                    UnicodeFinding(
                        index=index,
                        codepoint=ord(char),
                        name=unicodedata.name(char, "UNKNOWN"),
                    )
                )
    except UnicodeDecodeError as exc:
        decode_error = str(exc)

    try:
        normalized = normalize_text(data)
        would_change = normalized != data
    except UnicodeDecodeError:
        would_change = False

    return FileReport(
        path=path,
        lf_count=lf_count,
        cr_count=cr_count,
        crlf_count=crlf_count,
        lone_cr_count=lone_cr_count,
        ends_with_newline=ends_with_newline,
        has_bom=has_bom,
        unicode_findings=unicode_findings,
        collapsed_multiline=collapsed_multiline,
        decode_error=decode_error,
        would_change=would_change,
    )


def line_column(text: str, index: int) -> tuple[int, int]:
    line = text.count("\n", 0, index) + 1
    last_newline = text.rfind("\n", 0, index)
    column = index + 1 if last_newline == -1 else index - last_newline
    return line, column


def print_report(report: FileReport, root: Path) -> None:
    relative = report.path.relative_to(root).as_posix()
    print(
        f"{relative}: LF={report.lf_count} CR={report.cr_count} "
        f"CRLF={report.crlf_count} lone_cr={report.lone_cr_count > 0} "
        f"final_newline={report.ends_with_newline} "
        f"collapsed_multiline={report.collapsed_multiline} "
        f"suspicious_unicode={report.has_suspicious_unicode} "
        f"would_change={report.would_change}"
    )
    if report.decode_error:
        print(f"  decode_error: {report.decode_error}")
    if report.has_bom:
        print("  byte_offset=0 pattern=UTF-8-BOM")
    if report.unicode_findings:
        text = report.path.read_text(encoding="utf-8", errors="replace")
        for finding in report.unicode_findings[:20]:
            line, column = line_column(text, finding.index)
            print(
                f"  line={line} column={column} char_index={finding.index} "
                f"codepoint=U+{finding.codepoint:04X} name={finding.name}"
            )
        if len(report.unicode_findings) > 20:
            remaining = len(report.unicode_findings) - 20
            print(f"  ... {remaining} more suspicious Unicode finding(s)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize tracked text files to LF and remove invisible Unicode."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report files that need normalization without writing changes.",
    )
    parser.add_argument(
        "--quiet-clean",
        action="store_true",
        help="Only print per-file details for files with issues.",
    )
    args = parser.parse_args()

    root = repo_root()
    reports = [
        analyze_file(path)
        for path in tracked_files(root)
        if path.exists() and is_text_candidate(path, root)
    ]

    changed = 0
    for report in reports:
        if not args.quiet_clean or not report.is_clean or report.would_change:
            print_report(report, root)
        if not args.check and report.would_change:
            report.path.write_bytes(normalize_text(report.path.read_bytes()))
            changed += 1

    crlf_files = sum(1 for report in reports if report.crlf_count > 0)
    lone_cr_files = sum(1 for report in reports if report.lone_cr_count > 0)
    no_final_newline_files = sum(1 for report in reports if not report.ends_with_newline)
    suspicious_files = sum(1 for report in reports if report.has_suspicious_unicode)
    collapsed_files = sum(1 for report in reports if report.collapsed_multiline)
    dirty_files = sum(1 for report in reports if report.would_change)
    problem_files = sum(1 for report in reports if not report.is_clean or report.would_change)
    print(
        "SUMMARY "
        f"text_files={len(reports)} "
        f"would_change={dirty_files} "
        f"normalized={changed} "
        f"crlf_files={crlf_files} "
        f"lone_cr_files={lone_cr_files} "
        f"no_final_newline_files={no_final_newline_files} "
        f"suspicious_unicode_files={suspicious_files} "
        f"collapsed_multiline_files={collapsed_files}"
    )

    if args.check and problem_files:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
