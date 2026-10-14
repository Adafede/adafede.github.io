import shutil

import pytest
from PIL import Image

from scripts.site.optimize_artwork import optimize_artwork


def test_downsamples_single_frame_gif_to_webp(tmp_path):
    if not shutil.which("cwebp"):
        pytest.skip("cwebp is not installed")

    source = tmp_path / "artwork.gif"
    target = tmp_path / "artwork.webp"
    Image.new("RGB", (1200, 600), "white").save(source)

    assert optimize_artwork(source, target)
    with Image.open(target) as image:
        assert image.format == "WEBP"
        assert image.size == (320, 160)


def test_keeps_animated_gif_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: "cwebp")
    source = tmp_path / "animation.gif"
    target = tmp_path / "animation.webp"
    first = Image.new("RGB", (8, 8), "white")
    second = Image.new("RGB", (8, 8), "black")
    first.save(source, save_all=True, append_images=[second], duration=100, loop=0)

    assert not optimize_artwork(source, target)
    assert not target.exists()


def test_rasterizes_large_svg_preview(tmp_path):
    if not shutil.which("cwebp") or not shutil.which("rsvg-convert"):
        pytest.skip("cwebp and rsvg-convert are required")

    source = tmp_path / "large.svg"
    target = tmp_path / "large.webp"
    source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900">'
        '<rect width="1600" height="900" fill="teal"/></svg>',
    )
    source.write_bytes(source.read_bytes() + b" " * 100_000)

    assert optimize_artwork(source, target)
    with Image.open(target) as image:
        assert image.format == "WEBP"
        assert image.size == (320, 180)
