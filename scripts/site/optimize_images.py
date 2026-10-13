"""
Optimise the post screenshots for the Eleventy build.

The Eleventy build serves these directly, so this emits WebP with
intrinsic dimensions. Eleventy has no asset pipeline, so a raw 220 KB PNG becomes
the Largest Contentful Paint on post pages — Lighthouse flags both the byte
weight and the unsized image. This writes WebP copies into public/images/ and
repoints the generated Markdown at them.

The Eleventy build is unaffected otherwise: it serves these from
same source ONGs under images/.

Requires cwebp (libwebp) and sips; both are present on macOS with Homebrew and on
Linux via libwebp-tools. Skipped cleanly when absent.

Run: uv run python scripts/site/optimize_images.py
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = PROJECT_ROOT / "images" / "screenshots"
TARGET_DIR = PROJECT_ROOT / "public" / "images" / "screenshots"
BLOG_DIR = PROJECT_ROOT / "src" / "content" / "posts"

IMAGE_RE = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\(/images/screenshots/(?P<name>[^)]+)\.png\)",
)


def dimensions(path: Path) -> str | None:
    """`1872x1096` via sips, which is present on macOS."""
    try:
        out = subprocess.run(
            ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    width = height = None
    for line in out.splitlines():
        if "pixelWidth" in line:
            width = line.split(":")[-1].strip()
        elif "pixelHeight" in line:
            height = line.split(":")[-1].strip()
    return f"{width}x{height}" if width and height else None


def main() -> int:
    if not shutil.which("cwebp"):
        print("  ! cwebp not installed; Eleventy will ship the raw ONGs")
        return 0
    if not SOURCE_DIR.exists():
        return 0

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    names = []

    for source in sorted(SOURCE_DIR.glob("*.png")):
        stem = source.stem
        target = TARGET_DIR / f"{stem}.webp"
        # -m6 is the slowest/best method; these run once per sync.
        subprocess.run(
            ["cwebp", "-quiet", "-q", "82", "-m", "6", str(source), "-o", str(target)],
            check=True,
        )
        names.append((stem, dimensions(source)))

    if BLOG_DIR.exists():
        for post in sorted(BLOG_DIR.glob("*.md")):
            text = post.read_text(encoding="utf-8")
            changed = False

            def replace(match: re.Match) -> str:
                stem = match.group("name")
                dims = dict(names).get(stem)
                src = f"/images/screenshots/{stem}.webp"
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
                    f"    {post.relative_to(PROJECT_ROOT)}: {len(names)} screenshot(s) -> webp",
                )

    total = sum(p.stat().st_size for p in TARGET_DIR.glob("*.webp"))
    original = sum(p.stat().st_size for p in SOURCE_DIR.glob("*.png"))
    print(
        f"  + public/images/screenshots/*.webp ({original // 1024} KB -> {total // 1024} KB)",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
