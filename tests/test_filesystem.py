"""FileSystem path handling."""

from pathlib import Path

import pytest

from scripts.infrastructure.filesystem import FileSystem


@pytest.mark.parametrize(
    ("stem", "expected"),
    [
        ("2024-01-02_ok", True),
        ("2024-12-31_ok", True),
        ("2020-02-29_leap", True),
        ("2024-02-30_nonexistent_day", False),
        ("2024-13-01_month_13", False),
        ("2024-00-00_month_00", False),
        ("2024-19-39_month_19", False),
    ],
)
def test_only_real_calendar_dates_are_found(
    tmp_path: Path,
    stem: str,
    expected: bool,
):
    """A date-shaped filename that cannot exist must not be treated as a post.

    Its date used to be read back as data and written into `date:` frontmatter.
    """
    (tmp_path / "posts").mkdir()
    (tmp_path / "posts" / f"{stem}.qmd").write_text("x", encoding="utf-8")

    found = FileSystem(tmp_path).find_posts("posts")
    assert bool(found) is expected


def test_a_path_outside_the_root_is_rejected(tmp_path: Path):
    """`root / Path("/etc/x")` is `/etc/x`, so a non-relative path was silently
    resolved outside the site root and then skipped by the exists() guard."""
    fs = FileSystem(tmp_path)
    with pytest.raises(ValueError, match="relative to the site root"):
        fs.get_html_path(Path("/etc/passwd.qmd"), "posts")


def test_a_path_inside_the_root_resolves_under_the_site_dir(tmp_path: Path):
    fs = FileSystem(tmp_path)
    (tmp_path / "posts").mkdir()
    post = tmp_path / "posts" / "2024-01-02_x.qmd"
    post.write_text("---\ntitle: x\n---\n", encoding="utf-8")

    assert (
        fs.get_html_path(post, "posts")
        == tmp_path / "posts" / "posts" / "2024-01-02_x.html"
    )


def test_posts_are_returned_oldest_first(tmp_path: Path):
    """Ordering must not depend on what the filesystem's readdir hands back."""
    (tmp_path / "posts").mkdir()
    for stem in ("2024-03-01_c", "2024-01-02_a", "2024-02-01_b"):
        (tmp_path / "posts" / f"{stem}.qmd").write_text("x", encoding="utf-8")

    found = FileSystem(tmp_path).find_posts("posts")
    assert [p.name for p in found] == [
        "2024-01-02_a.qmd",
        "2024-02-01_b.qmd",
        "2024-03-01_c.qmd",
    ]
