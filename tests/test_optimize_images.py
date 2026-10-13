import struct

from scripts.site import optimize_images


def test_preserves_png_dimensions_without_webp_converter(tmp_path, monkeypatch):
    source_dir = tmp_path / "screenshots"
    posts_dir = tmp_path / "posts"
    source_dir.mkdir()
    posts_dir.mkdir()
    image = source_dir / "sample.png"
    image.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">II", 1872, 1096),
    )
    post = posts_dir / "post.md"
    post.write_text("![Screenshot](/images/screenshots/sample.png)\n")

    monkeypatch.setattr(optimize_images, "SOURCE_DIR", source_dir)
    monkeypatch.setattr(optimize_images, "TARGET_DIR", tmp_path / "public")
    monkeypatch.setattr(optimize_images, "BLOG_DIR", posts_dir)
    monkeypatch.setattr(optimize_images, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(optimize_images.shutil, "which", lambda _: None)

    optimize_images.main()

    assert 'width="1872" height="1096"' in post.read_text()
