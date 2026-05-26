#!/usr/bin/env python3
"""
Process photos dropped in ./upload/ and add them to the gallery.

For each image in upload/ (top level only):
  - writes images/large/{stem}.jpg and images/thumbnails/{stem}.jpg
  - appends an entry to LR.images in index.html
  - moves the source file to upload/processed/

Use --private for upload/private/ -> images/private/ and private/index.html.

Usage (from repository root):
  pip install -r scripts/requirements.txt
  python scripts/add_photos.py
  python scripts/add_photos.py --private
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

from io import BytesIO

from PIL import Image

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from private_crypto import encrypt_file_bytes, load_password

REPO_ROOT = SCRIPTS_DIR.parent

LARGE_MAX = 1200
THUMB_MAX = 400
JPEG_QUALITY = 85
THUMB_QUALITY = 80

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}

LR_IMAGES_PATTERN = re.compile(
    r"(LR\.images = \[)(.*?)(\n\s*\])",
    re.DOTALL,
)
EXISTING_IDS = re.compile(r'"id": "(\d+)"')
EXISTING_EXPORT = re.compile(r'"exportFilename": "([^"]+)"')


def next_image_id(html: str) -> str:
    ids = [int(m) for m in EXISTING_IDS.findall(html)]
    return str(max(ids, default=100000) + 1)


def export_filename_in_gallery(html: str, name: str) -> bool:
    return name in EXISTING_EXPORT.findall(html)


def save_resized_jpeg(src: Image.Image, dest: Path, max_side: int, quality: int) -> tuple[int, int]:
    img = src.copy()
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, "JPEG", quality=quality, optimize=True)
    return img.size


def save_resized_jpeg_encrypted(
    src: Image.Image,
    dest: Path,
    max_side: int,
    quality: int,
    password: str,
) -> tuple[int, int]:
    img = src.copy()
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    buffer = BytesIO()
    img.save(buffer, "JPEG", quality=quality, optimize=True)
    dest.write_bytes(encrypt_file_bytes(buffer.getvalue(), password))
    return img.size


def format_lr_entry(image_id: str, width: int, height: int, export_filename: str) -> str:
    return (
        f'{{"id": "{image_id}", "largeWidth": "{width}", "largeHeight": "{height}", '
        f'"exportFilename": "{export_filename}", "title": "", "caption" : ""}}'
    )


def append_lr_entry(html: str, entry: str) -> str:
    match = LR_IMAGES_PATTERN.search(html)
    if not match:
        raise ValueError("Could not find LR.images array in index.html")

    _prefix, body, _suffix = match.groups()
    body = body.rstrip()
    if body and not body.endswith(","):
        body += ","
    new_body = f"{body}\n                         {entry},"

    start, end = match.span(2)
    return html[:start] + new_body + html[end:]


def upload_files(upload_dir: Path) -> list[Path]:
    if not upload_dir.is_dir():
        upload_dir.mkdir(parents=True, exist_ok=True)
        return []

    files = []
    for path in sorted(upload_dir.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        files.append(path)
    return files


def process_file(
    path: Path,
    html: str,
    large_dir: Path,
    thumb_dir: Path,
    processed_dir: Path,
    *,
    encrypted: bool = False,
    password: str | None = None,
) -> tuple[str, bool]:
    export_filename = path.stem
    ext = ".enc" if encrypted else ".jpg"
    large_path = large_dir / f"{export_filename}{ext}"
    thumb_path = thumb_dir / f"{export_filename}{ext}"

    if export_filename_in_gallery(html, export_filename):
        print(f"  skip {path.name}: already in index.html")
        return html, False

    if large_path.exists() or thumb_path.exists():
        print(f"  skip {path.name}: output file already exists")
        return html, False

    with Image.open(path) as img:
        if encrypted:
            if not password:
                raise ValueError("password required for encrypted private images")
            large_w, large_h = save_resized_jpeg_encrypted(
                img, large_path, LARGE_MAX, JPEG_QUALITY, password
            )
            save_resized_jpeg_encrypted(img, thumb_path, THUMB_MAX, THUMB_QUALITY, password)
        else:
            large_w, large_h = save_resized_jpeg(img, large_path, LARGE_MAX, JPEG_QUALITY)
            save_resized_jpeg(img, thumb_path, THUMB_MAX, THUMB_QUALITY)

    image_id = next_image_id(html)
    entry = format_lr_entry(image_id, large_w, large_h, export_filename)
    html = append_lr_entry(html, entry)

    processed_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(processed_dir / path.name))

    print(f"  added {export_filename}{ext} ({large_w}x{large_h}, id={image_id})")
    return html, True


def resolve_paths(private: bool) -> tuple[Path, Path, Path, Path, Path]:
    if private:
        upload_dir = REPO_ROOT / "upload" / "private"
        processed_dir = upload_dir / "processed"
        large_dir = REPO_ROOT / "images" / "private" / "encrypted" / "large"
        thumb_dir = REPO_ROOT / "images" / "private" / "encrypted" / "thumbnails"
        index_html = REPO_ROOT / "private" / "index.html"
    else:
        upload_dir = REPO_ROOT / "upload"
        processed_dir = upload_dir / "processed"
        large_dir = REPO_ROOT / "images" / "large"
        thumb_dir = REPO_ROOT / "images" / "thumbnails"
        index_html = REPO_ROOT / "index.html"
    return upload_dir, processed_dir, large_dir, thumb_dir, index_html


def main() -> int:
    parser = argparse.ArgumentParser(description="Add uploaded photos to the gallery.")
    parser.add_argument(
        "--private",
        action="store_true",
        help="Use upload/private/ and update private/index.html",
    )
    args = parser.parse_args()

    upload_dir, processed_dir, large_dir, thumb_dir, index_html = resolve_paths(args.private)
    files = upload_files(upload_dir)
    if not files:
        print(f"No images in {upload_dir.relative_to(REPO_ROOT)}/")
        print("Drop files there (basename becomes exportFilename), then run again.")
        return 0

    password = load_password() if args.private else None
    html = index_html.read_text(encoding="utf-8")
    added = 0

    for path in files:
        print(f"Processing {path.name}...")
        try:
            html, changed = process_file(
                path,
                html,
                large_dir,
                thumb_dir,
                processed_dir,
                encrypted=args.private,
                password=password,
            )
            if changed:
                added += 1
        except Exception as exc:
            print(f"  error: {exc}", file=sys.stderr)
            return 1

    if added:
        index_html.write_text(html, encoding="utf-8", newline="\n")
        print(f"\nUpdated {index_html.relative_to(REPO_ROOT)} ({added} photo(s)).")
        label = (
            "images/private/encrypted/ and private/"
            if args.private
            else "images/ and index.html"
        )
        print(f"Commit {label} when ready.")
    else:
        print("\nNo changes made.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
