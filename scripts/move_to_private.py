#!/usr/bin/env python3
"""
Move photos from the public gallery to the private (encrypted) gallery.

Paste exportFilename values into private/to_private.txt (one per line), then run
from the repository root:

  python scripts/move_to_private.py

Requires private/.gallery-password (or PRIVATE_GALLERY_PASSWORD) for encryption.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from private_crypto import encrypt_file_bytes, load_password

REPO_ROOT = SCRIPTS_DIR.parent
NAMES_FILE = REPO_ROOT / "private" / "to_private.txt"
LOG_FILE = REPO_ROOT / "private" / "move_to_private.log"

PUBLIC_INDEX = REPO_ROOT / "index.html"
PRIVATE_INDEX = REPO_ROOT / "private" / "index.html"
PUBLIC_LARGE = REPO_ROOT / "images" / "large"
PUBLIC_THUMB = REPO_ROOT / "images" / "thumbnails"
PRIVATE_LARGE = REPO_ROOT / "images" / "private" / "encrypted" / "large"
PRIVATE_THUMB = REPO_ROOT / "images" / "private" / "encrypted" / "thumbnails"

LR_IMAGES_PATTERN = re.compile(
    r"(LR\.images = \[)(.*?)(\n\s*\])",
    re.DOTALL,
)
EXISTING_EXPORT = re.compile(r'"exportFilename": "([^"]+)"')


def normalize_name(line: str) -> str | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    name = Path(line).stem
    return name or None


def read_names() -> list[str]:
    if not NAMES_FILE.is_file():
        NAMES_FILE.parent.mkdir(parents=True, exist_ok=True)
        NAMES_FILE.write_text(
            "# One exportFilename per line (with or without .jpg)\n# IMG_5950\n",
            encoding="utf-8",
        )
        return []
    names: list[str] = []
    for line in NAMES_FILE.read_text(encoding="utf-8").splitlines():
        name = normalize_name(line)
        if name and name not in names:
            names.append(name)
    return names


def export_in_gallery(html: str, export_filename: str) -> bool:
    return export_filename in EXISTING_EXPORT.findall(html)


def extract_lr_entry(html: str, export_filename: str) -> tuple[str, str]:
    pattern = re.compile(
        rf'\n\s*(\{{[^{{}}]*"exportFilename": "{re.escape(export_filename)}"[^{{}}]*\}}),?',
    )
    match = pattern.search(html)
    if not match:
        return html, ""
    entry = match.group(1).strip()
    new_html = pattern.sub("", html, count=1)
    return new_html, entry


def append_lr_entry(html: str, entry: str) -> str:
    match = LR_IMAGES_PATTERN.search(html)
    if not match:
        raise ValueError("Could not find LR.images array in private/index.html")

    _prefix, body, _suffix = match.groups()
    body = body.rstrip()
    if body and not body.endswith(","):
        body += ","
    new_body = f"{body}\n                         {entry},"

    start, end = match.span(2)
    return html[:start] + new_body + html[end:]


def encrypt_jpeg_file(src: Path, dest: Path, password: str) -> bool:
    if not src.is_file():
        return False
    if dest.exists():
        raise FileExistsError(f"private file already exists: {dest.relative_to(REPO_ROOT)}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(encrypt_file_bytes(src.read_bytes(), password))
    src.unlink()
    return True


def move_photo(
    export_filename: str,
    public_html: str,
    private_html: str,
    password: str,
) -> tuple[str, str, list[str]]:
    actions: list[str] = []

    if not export_in_gallery(public_html, export_filename):
        raise ValueError("not in public index.html")

    if export_in_gallery(private_html, export_filename):
        raise ValueError("already in private index.html")

    public_html, entry = extract_lr_entry(public_html, export_filename)
    if not entry:
        raise ValueError("could not extract LR.images entry from index.html")

    large_src = PUBLIC_LARGE / f"{export_filename}.jpg"
    thumb_src = PUBLIC_THUMB / f"{export_filename}.jpg"
    large_dest = PRIVATE_LARGE / f"{export_filename}.enc"
    thumb_dest = PRIVATE_THUMB / f"{export_filename}.enc"

    if not large_src.exists() and not thumb_src.exists():
        raise ValueError("no public JPEG files found")

    if encrypt_jpeg_file(large_src, large_dest, password):
        actions.append(f"encrypted large -> images/private/encrypted/large/{export_filename}.enc")
    if encrypt_jpeg_file(thumb_src, thumb_dest, password):
        actions.append(f"encrypted thumb -> images/private/encrypted/thumbnails/{export_filename}.enc")

    if not actions:
        raise ValueError("no image files were moved")

    private_html = append_lr_entry(private_html, entry)
    actions.append("removed from index.html")
    actions.append("added to private/index.html")

    return public_html, private_html, actions


def log_move(export_filename: str, actions: list[str]) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [f"{timestamp}  {export_filename}"] + [f"  - {a}" for a in actions]
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_remaining_names(failed: list[str]) -> None:
    header = "# One exportFilename per line (with or without .jpg)\n"
    body = "\n".join(failed)
    NAMES_FILE.write_text(header + (body + "\n" if body else ""), encoding="utf-8")


def main() -> int:
    names = read_names()
    if not names:
        print(f"No names in {NAMES_FILE.relative_to(REPO_ROOT)}.")
        print("Paste exportFilename values (one per line), then run again.")
        return 0

    try:
        password = load_password()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    public_html = PUBLIC_INDEX.read_text(encoding="utf-8")
    private_html = PRIVATE_INDEX.read_text(encoding="utf-8")
    moved = 0
    failed: list[str] = []

    for name in names:
        print(f"Moving {name} to private...")
        try:
            public_html, private_html, actions = move_photo(
                name, public_html, private_html, password
            )
            for action in actions:
                print(f"  {action}")
            log_move(name, actions)
            moved += 1
        except Exception as exc:
            print(f"  error: {exc}", file=sys.stderr)
            failed.append(name)

    if moved:
        PUBLIC_INDEX.write_text(public_html, encoding="utf-8", newline="\n")
        PRIVATE_INDEX.write_text(private_html, encoding="utf-8", newline="\n")
        print(f"\nUpdated index.html and private/index.html ({moved} moved).")
        print("Commit index.html, private/, and images/ when ready.")

    write_remaining_names(failed)

    if failed:
        print(f"\n{len(failed)} name(s) left in {NAMES_FILE.relative_to(REPO_ROOT)} for retry.")
        return 1 if moved == 0 else 0

    print(f"\nCleared {NAMES_FILE.relative_to(REPO_ROOT)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
