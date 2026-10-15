"""Create compact WebP previews for artwork displayed in article and Varia cards."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

# The card box is 11rem (176 CSS px) wide, so 512px covers a 2x display with
# room to spare and stays sharp on a 3x phone. 320px was only 1.8x, which reads
# as a soft thumbnail on exactly the devices most likely to be looking at it.
MAX_SIZE = (512, 512)


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
    """Downsample raster artwork for a card preview; preserve animation.

    Vectors are not accepted. Rasterizing a vector trades away the scaling and the
    sharpness it was published in, so SVGs are served as they were authored.
    """
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
