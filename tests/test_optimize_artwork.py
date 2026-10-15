import shutil

import pytest
from PIL import Image

from scripts.site.optimize_artwork import MAX_SIZE, optimize_artwork


def test_downsamples_single_frame_gif_to_webp(tmp_path):
    if not shutil.which("cwebp"):
        pytest.skip("cwebp is not installed")

    source = tmp_path / "artwork.gif"
    target = tmp_path / "artwork.webp"
    Image.new("RGB", (1200, 600), "white").save(source)

    assert optimize_artwork(source, target)
    with Image.open(target) as image:
        assert image.format == "WEBP"
        assert image.size == (MAX_SIZE[0], MAX_SIZE[0] // 2)


def test_keeps_animated_gif_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: "cwebp")
    source = tmp_path / "animation.gif"
    target = tmp_path / "animation.webp"
    first = Image.new("RGB", (8, 8), "white")
    second = Image.new("RGB", (8, 8), "black")
    first.save(source, save_all=True, append_images=[second], duration=100, loop=0)

    assert not optimize_artwork(source, target)
    assert not target.exists()


def test_refuses_to_rasterize_a_vector(tmp_path):
    """The whole point: an SVG goes out as an SVG, at any size."""
    source = tmp_path / "logo.svg"
    target = tmp_path / "logo.webp"
    source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900">'
        '<rect width="1600" height="900" fill="teal"/></svg>',
    )

    assert not optimize_artwork(source, target)
    assert not target.exists()
