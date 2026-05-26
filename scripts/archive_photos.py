#!/usr/bin/env python3
"""
Archive gallery photos listed in archive/names.txt.

For each name (one per line, exportFilename with or without .jpg):
  - moves images/large/{name}.jpg and images/thumbnails/{name}.jpg to archive/
  - removes the matching LR.images entry from index.html

Paste names into archive/names.txt, then run from the repository root:
  python scripts/archive_photos.py
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NAMES_FILE = REPO_ROOT / "archive" / "names.txt"
ARCHIVE_LARGE = REPO_ROOT / "archive" / "large"
ARCHIVE_THUMB = REPO_ROOT / "archive" / "thumbnails"
LARGE_DIR = REPO_ROOT / "images" / "large"
THUMB_DIR = REPO_ROOT / "images" / "thumbnails"
INDEX_HTML = REPO_ROOT / "index.html"
LOG_FILE = REPO_ROOT / "archive" / "archive.log"


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
    names = []
    for line in NAMES_FILE.read_text(encoding="utf-8").splitlines():
        name = normalize_name(line)
        if name and name not in names:
            names.append(name)
    return names


def remove_lr_entry(html: str, export_filename: str) -> tuple[str, bool]:
    pattern = re.compile(
        rf'\n\s*\{{[^{{}}]*"exportFilename": "{re.escape(export_filename)}"[^{{}}]*\}},?',
    )
    new_html, count = pattern.subn("", html, count=1)
    return new_html, count > 0


def move_image(src: Path, dest: Path) -> bool:
    if not src.is_file():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise FileExistsError(f"archive file already exists: {dest.relative_to(REPO_ROOT)}")
    src.rename(dest)
    return True


def archive_photo(export_filename: str, html: str) -> tuple[str, list[str]]:
    actions: list[str] = []
    large_src = LARGE_DIR / f"{export_filename}.jpg"
    thumb_src = THUMB_DIR / f"{export_filename}.jpg"
    large_dest = ARCHIVE_LARGE / f"{export_filename}.jpg"
    thumb_dest = ARCHIVE_THUMB / f"{export_filename}.jpg"

    in_gallery = f'"exportFilename": "{export_filename}"' in html
    if not in_gallery and not large_src.exists() and not thumb_src.exists():
        raise ValueError("not in gallery and no image files found")

    moved_large = move_image(large_src, large_dest)
    moved_thumb = move_image(thumb_src, thumb_dest)
    if moved_large:
        actions.append(f"moved large -> archive/large/{export_filename}.jpg")
    if moved_thumb:
        actions.append(f"moved thumb -> archive/thumbnails/{export_filename}.jpg")

    html, removed = remove_lr_entry(html, export_filename)
    if removed:
        actions.append("removed from index.html")
    elif in_gallery:
        raise ValueError("in gallery but could not remove index.html entry")

    if not actions:
        raise ValueError("nothing to do")

    return html, actions


def log_archive(export_filename: str, actions: list[str]) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [f"{timestamp}  {export_filename}"] + [f"  - {a}" for a in actions]
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_remaining_names(failed: list[str]) -> None:
    header = "# One exportFilename per line (with or without .jpg)\n"
    body = "\n".join(failed)
    content = header + (body + "\n" if body else "")
    NAMES_FILE.write_text(content, encoding="utf-8")


def main() -> int:
    names = read_names()
    if not names:
        print(f"No names in {NAMES_FILE.relative_to(REPO_ROOT)}.")
        print("Paste exportFilename values (one per line), then run again.")
        return 0

    html = INDEX_HTML.read_text(encoding="utf-8")
    archived = 0
    failed: list[str] = []

    for name in names:
        print(f"Archiving {name}...")
        try:
            html, actions = archive_photo(name, html)
            for action in actions:
                print(f"  {action}")
            log_archive(name, actions)
            archived += 1
        except Exception as exc:
            print(f"  error: {exc}", file=sys.stderr)
            failed.append(name)

    if archived:
        INDEX_HTML.write_text(html, encoding="utf-8", newline="\n")
        print(f"\nUpdated {INDEX_HTML.relative_to(REPO_ROOT)} ({archived} archived).")
        print("Commit index.html, archive/, and images/ changes when ready.")

    write_remaining_names(failed)

    if failed:
        print(f"\n{len(failed)} name(s) left in {NAMES_FILE.relative_to(REPO_ROOT)} for retry.")
        return 1 if archived == 0 else 0

    print(f"\nCleared {NAMES_FILE.relative_to(REPO_ROOT)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
