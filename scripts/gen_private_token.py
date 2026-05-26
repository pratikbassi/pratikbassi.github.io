#!/usr/bin/env python3
"""Print the AUTH_TOKEN for assets/js/private-gate.js from a password."""

from __future__ import annotations

import hashlib
import sys

SALT = "pratik-private-v1"


def token_for_password(password: str) -> str:
    return hashlib.sha256(f"{SALT}:{password}".encode()).hexdigest()


def main() -> int:
    if len(sys.argv) > 1:
        password = sys.argv[1]
    else:
        password = input("Password: ")
    print(token_for_password(password))
    print("\nPaste into AUTH_TOKEN in assets/js/private-gate.js")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
