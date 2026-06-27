#!/usr/bin/env python3
"""Scan tracked text files for hidden Unicode and non-LF line endings."""

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
class Finding:
    path: Path
    line: int | None
    column: int | None
    byte_offset: int
    pattern: str
    name: str
    context: str


def repo_root(root_arg: str | None) -> Path:
    if root_arg:
        return Path(root_arg).resolve()
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


def line_column_from_bytes(data: bytes, byte_offset: int) -> tuple[int, int]:
    prefix = data[:byte_offset]
    line = prefix.count(b"\n") + 1
    last_newline = prefix.rfind(b"\n")
    column = byte_offset + 1 if last_newline == -1 else byte_offset - last_newline
    return line, column


def render_context_bytes(data: bytes, byte_offset: int, width: int = 1) -> str:
    radius = 32
    start = max(0, byte_offset - radius)
    end = min(len(data), byte_offset + max(width, 1) + radius)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(data) else ""
    before = render_bytes(data[start:byte_offset])
    target = render_bytes(data[byte_offset : byte_offset + width])
    after = render_bytes(data[byte_offset + width : end])
    return f"{prefix}{before}[{target}]{after}{suffix}"


def render_bytes(data: bytes) -> str:
    text = data.decode("utf-8", errors="replace")
    return (
        text.replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )


def suspicious_codepoint(char: str) -> tuple[str, str] | None:
    codepoint = ord(char)
    category = unicodedata.category(char)
    if codepoint in ALLOWED_CONTROL_CODEPOINTS:
        return None
    if char == "\r":
        return None
    if codepoint == 0x00A0:
        return f"U+{codepoint:04X}", unicodedata.name(char, "UNKNOWN")
    if 0x2000 <= codepoint <= 0x200A:
        return f"U+{codepoint:04X}", unicodedata.name(char, "UNKNOWN")
    if codepoint in {0x2028, 0x2029, 0xFEFF}:
        return f"U+{codepoint:04X}", unicodedata.name(char, "UNKNOWN")
    if category == "Cf":
        return f"U+{codepoint:04X}", unicodedata.name(char, "UNKNOWN")
    if category == "Cc":
        return f"U+{codepoint:04X}", unicodedata.name(char, "UNKNOWN")
    if category in {"Zl", "Zp"}:
        return f"U+{codepoint:04X}", unicodedata.name(char, "UNKNOWN")
    if category == "Zs" and codepoint != 0x0020:
        return f"U+{codepoint:04X}", unicodedata.name(char, "UNKNOWN")
    return None


def scan_file(path: Path) -> list[Finding]:
    data = path.read_bytes()
    findings: list[Finding] = []

    if data.startswith(b"\xef\xbb\xbf"):
        findings.append(byte_finding(path, data, 0, 3, "UTF-8-BOM", "BYTE ORDER MARK"))

    offset = 0
    while True:
        crlf_offset = data.find(b"\r\n", offset)
        if crlf_offset == -1:
            break
        findings.append(byte_finding(path, data, crlf_offset, 2, "CRLF", "CRLF line ending"))
        offset = crlf_offset + 2

    for index, value in enumerate(data):
        if value == 0x0D:
            next_byte = data[index + 1] if index + 1 < len(data) else None
            if next_byte != 0x0A:
                findings.append(byte_finding(path, data, index, 1, "LONE_CR", "lone carriage return"))

    if not data.endswith(b"\n"):
        line, column = line_column_from_bytes(data, len(data))
        findings.append(
            Finding(
                path=path,
                line=line,
                column=column,
                byte_offset=len(data),
                pattern="NO_FINAL_NEWLINE",
                name="file does not end with LF",
                context=render_context_bytes(data, max(0, len(data) - 1), 1)
                if data
                else "[EOF]",
            )
        )

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        findings.append(
            Finding(
                path=path,
                line=None,
                column=None,
                byte_offset=exc.start,
                pattern="UTF8_DECODE_ERROR",
                name=str(exc),
                context=render_context_bytes(data, exc.start, max(1, exc.end - exc.start)),
            )
        )
        return findings

    byte_offset = 0
    for char in text:
        suspicious = suspicious_codepoint(char)
        char_bytes = char.encode("utf-8")
        if suspicious:
            line, column = line_column_from_bytes(data, byte_offset)
            pattern, name = suspicious
            findings.append(
                Finding(
                    path=path,
                    line=line,
                    column=column,
                    byte_offset=byte_offset,
                    pattern=pattern,
                    name=name,
                    context=render_context_bytes(data, byte_offset, len(char_bytes)),
                )
            )
        byte_offset += len(char_bytes)

    return findings


def byte_finding(
    path: Path,
    data: bytes,
    byte_offset: int,
    width: int,
    pattern: str,
    name: str,
) -> Finding:
    line, column = line_column_from_bytes(data, byte_offset)
    return Finding(
        path=path,
        line=line,
        column=column,
        byte_offset=byte_offset,
        pattern=pattern,
        name=name,
        context=render_context_bytes(data, byte_offset, width),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan tracked text files for CR line endings and hidden Unicode."
    )
    parser.add_argument("--root", default=None, help="Repository root to scan.")
    args = parser.parse_args()

    root = repo_root(args.root)
    findings: list[Finding] = []
    for path in sorted(tracked_files(root)):
        if path.exists() and is_text_candidate(path, root):
            findings.extend(scan_file(path))

    if findings:
        print("Hidden Unicode or line-ending findings:")
        for finding in findings:
            relative = finding.path.relative_to(root).as_posix()
            location = (
                f"{relative}:{finding.line}:{finding.column}"
                if finding.line is not None and finding.column is not None
                else f"{relative}:?:?"
            )
            print(
                f"{location}: byte={finding.byte_offset} "
                f"{finding.pattern} {finding.name} | {finding.context}"
            )
        return 1

    print("No hidden Unicode, CR line endings, or final-newline issues found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
