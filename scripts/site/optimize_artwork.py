"""Create compact WebP previews for artwork displayed in article cards."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

MAX_SIZE = (400, 400)
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
    """Downsample static GIFs and large SVGs; preserve animated GIFs."""
    cwebp = shutil.which("cwebp")
    if not cwebp:
        return False

    with tempfile.TemporaryDirectory() as directory:
        png = Path(directory) / "artwork.png"
        if source.suffix.lower() == ".gif":
            with Image.open(source) as image:
                if image.format != "GIF":
                    return False
                try:
                    image.seek(1)
                except EOFError:
                    pass
                else:
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
        encode_webp(png, target)
    return True


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: optimize_artwork.py SOURCE TARGET.webp")
    if not optimize_artwork(Path(sys.argv[1]), Path(sys.argv[2])):
        raise SystemExit(2)
