"""Create compact WebP previews for artwork displayed in article and Varia cards."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

MAX_SIZE = (320, 320)
SVG_MIN_SIZE = 100_000


def encode_webp(png: Path, target: Path) -> None:
    subprocess.run(
        [
            "cwebp",
            "-quiet",
            "-q",
            "88",
            "-m",
            "6",
            "-metadata",
            "none",
            str(png),
            "-o",
            str(target),
        ],
        check=True,
    )


def optimize_artwork(source: Path, target: Path) -> bool:
    """Downsample static raster artwork and large SVGs; preserve animation."""
    cwebp = shutil.which("cwebp")
    if not cwebp:
        return False

    with tempfile.TemporaryDirectory() as directory:
        png = Path(directory) / "artwork.png"
        if source.suffix.lower() in {".gif", ".png"}:
            with Image.open(source) as image:
                expected_format = source.suffix[1:].upper()
                if image.format != expected_format:
                    return False
                if getattr(image, "n_frames", 1) > 1:
                    return False
                image.seek(0)
                frame = image.convert("RGBA")
            frame.thumbnail(MAX_SIZE, Image.Resampling.LANCZOS)
            frame.save(png)
        elif source.suffix.lower() == ".svg" and source.stat().st_size >= SVG_MIN_SIZE:
            rsvg_convert = shutil.which("rsvg-convert")
            if not rsvg_convert:
                return False
            subprocess.run(
                [
                    rsvg_convert,
                    "--width",
                    str(MAX_SIZE[0]),
                    str(source),
                    "-o",
                    str(png),
                ],
                check=True,
            )
        else:
            return False
        with Image.open(png) as image:
            preview = image.convert("RGBA")
        preview.thumbnail(MAX_SIZE, Image.Resampling.LANCZOS)
        preview.save(png)
        encode_webp(png, target)
    if target.stat().st_size >= source.stat().st_size:
        target.unlink()
        return False
    return True


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: optimize_artwork.py SOURCE TARGET.webp")
    if not optimize_artwork(Path(sys.argv[1]), Path(sys.argv[2])):
        raise SystemExit(2)
