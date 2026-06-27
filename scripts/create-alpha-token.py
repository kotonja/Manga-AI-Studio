#!/usr/bin/env python3
"""Generate a private-alpha tester token pair.

This script only creates new token material. It never reads existing secrets,
never overwrites .env, and writes only to .alpha-tokens.generated when --write is
explicitly passed.
Generated token output is plain LF-delimited text for easy copying.
The script itself is intentionally stored as real LF-delimited text in Git.
"""

from __future__ import annotations

import argparse
import re
import secrets
from pathlib import Path


TOKEN_FILE = Path(".alpha-tokens.generated")


def normalize_user_id(value: str | None) -> str:
    if value:
        cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-")
        if cleaned:
            return cleaned[:80]
    return f"tester-{secrets.token_hex(3)}"


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an ALPHA_USER_TOKENS user-id:token pair.")
    parser.add_argument("--user", help="Optional tester id, for example tester-a.")
    parser.add_argument("--write", action="store_true", help="Append the generated pair to .alpha-tokens.generated.")
    args = parser.parse_args()

    pair = f"{normalize_user_id(args.user)}:{generate_token()}"
    print(pair)
    print()
    print("Copy generated pairs into ALPHA_USER_TOKENS, separated by commas, for example:")
    print(f"ALPHA_USER_TOKENS={pair}")

    if args.write:
        with TOKEN_FILE.open("a", encoding="utf-8") as handle:
            handle.write(f"{pair}\n")
        print(f"\nAppended to {TOKEN_FILE}. This file is gitignored; keep it private.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
