"""
Optimise the post screenshots for the Eleventy build.

The Eleventy build serves these directly, so this emits WebP with intrinsic
dimensions when cwebp is available. Otherwise it keeps the ONGs and still adds
their intrinsic dimensions to prevent layout shifts.

The original screenshots live under images/; WebP copies are written to
public/images/ when conversion is available.

Run: uv run python scripts/site/optimize_images.py
"""

from __future__ import annotations

import re
import shutil
import struct
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = PROJECT_ROOT / "images" / "screenshots"
TARGET_DIR = PROJECT_ROOT / "public" / "images" / "screenshots"
BLOG_DIR = PROJECT_ROOT / "src" / "content" / "posts"
MAX_DIMENSION = 1400

IMAGE_RE = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\(/images/screenshots/(?P<name>[^)]+)\.png\)",
)


def dimensions(path: Path) -> str | None:
    """Return the intrinsic dimensions of a PNG from its header."""
    try:
        with path.open("rb") as image:
            header = image.read(24)
    except OSError:
        return None

    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    width, height = struct.unpack(">II", header[16:24])
    return f"{width}x{height}" if width and height else None


def main() -> int:
    if not SOURCE_DIR.exists():
        return 0

    converter = shutil.which("cwebp")
    if converter:
        TARGET_DIR.mkdir(parents=True, exist_ok=True)
    else:
        print("  ! cwebp not installed; keeping ONGs with intrinsic dimensions")

    names = []

    for source in sorted(SOURCE_DIR.glob("*.png")):
        stem = source.stem
        size = dimensions(source)
        if converter:
            target = TARGET_DIR / f"{stem}.webp"
            # Keep enough pixels for a full-width, high-density display
            # without shipping the original multi-megapixel screenshot.
            width, height = map(int, size.split("x")) if size else (0, 0)
            longest_edge = max(width, height)
            scale = MAX_DIMENSION / longest_edge if longest_edge > MAX_DIMENSION else 1
            resize = (
                ["-resize", str(round(width * scale)), str(round(height * scale))]
                if scale < 1
                else []
            )
            subprocess.run(
                [
                    converter,
                    "-quiet",
                    "-q",
                    "82",
                    "-m",
                    "6",
                    *resize,
                    str(source),
                    "-o",
                    str(target),
                ],
                check=True,
            )
        names.append((stem, size))

    if BLOG_DIR.exists():
        for post in sorted(BLOG_DIR.glob("*.md")):
            text = post.read_text(encoding="utf-8")
            changed = False

            def replace(match: re.Match[str]) -> str:
                stem = match.group("name")
                dims = dict(names).get(stem)
                extension = "webp" if converter else "png"
                src = f"/images/screenshots/{stem}.{extension}"
                alt = match.group("alt")
                if not dims:
                    return f"![{alt}]({src})"
                width, height = dims.split("x")
                # Explicit dimensions let the browser reserve the box, which is
                # what removes the unsized-image finding and the layout shift.
                return f'<img src="{src}" alt="{alt}" width="{width}" height="{height}" loading="lazy" decoding="async">'

            updated = IMAGE_RE.sub(replace, text)
            if updated != text:
                post.write_text(updated, encoding="utf-8")
                changed = True

            if changed:
                print(
                    f"    {post.relative_to(PROJECT_ROOT)}: "
                    f"{'optimized to WebP' if converter else 'kept as PNG'} with dimensions",
                )

    if converter:
        total = sum(p.stat().st_size for p in TARGET_DIR.glob("*.webp"))
        original = sum(p.stat().st_size for p in SOURCE_DIR.glob("*.png"))
        print(
            f"  + public/images/screenshots/*.webp ({original // 1024} KB -> {total // 1024} KB)",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
