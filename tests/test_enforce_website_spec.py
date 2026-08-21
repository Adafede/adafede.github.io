"""Characterization tests for enforce_website_spec (head-tag hardening)."""

from pathlib import Path

from bs4 import BeautifulSoup

from scripts.utilities.enforce_website_spec import enforce_website_spec

SAMPLE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Test Page</title>
</head>
<body>
  <h1>Hello</h1>
</body>
</html>
"""


def _write_html(tmp_path: Path, name: str = "page.html") -> Path:
    # enforce_website_spec walks up to find a "_site" parent to compute routes,
    # so the file must live inside a _site directory tree.
    site = tmp_path / "_site"
    path = site / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(SAMPLE_HTML, encoding="utf-8")
    return path


def test_adds_canonical_link(tmp_path: Path):
    html_file = _write_html(tmp_path, "page.html")

    enforce_website_spec([html_file], site_url="https://adafede.github.io")

    soup = BeautifulSoup(html_file.read_text(encoding="utf-8"), "html.parser")
    canonical = soup.find("link", rel="canonical")
    assert canonical is not None
    assert canonical["href"] == "https://adafede.github.io/page.html"


def test_adds_description_meta(tmp_path: Path):
    html_file = _write_html(tmp_path)

    enforce_website_spec([html_file], site_url="https://adafede.github.io")

    soup = BeautifulSoup(html_file.read_text(encoding="utf-8"), "html.parser")
    desc = soup.find("meta", attrs={"name": "description"})
    assert desc is not None
    assert "Adriano Rutz" in desc["content"]


def test_adds_og_open_graph_tags(tmp_path: Path):
    html_file = _write_html(tmp_path)

    enforce_website_spec([html_file], site_url="https://adafede.github.io")

    soup = BeautifulSoup(html_file.read_text(encoding="utf-8"), "html.parser")
    for prop in ["og:title", "og:description", "og:url", "og:type", "og:image"]:
        assert soup.find("meta", attrs={"property": prop}) is not None, (
            f"missing {prop}"
        )


def test_adds_twitter_card_tags(tmp_path: Path):
    html_file = _write_html(tmp_path)

    enforce_website_spec([html_file], site_url="https://adafede.github.io")

    soup = BeautifulSoup(html_file.read_text(encoding="utf-8"), "html.parser")
    for name in [
        "twitter:card",
        "twitter:title",
        "twitter:description",
        "twitter:image",
    ]:
        assert soup.find("meta", attrs={"name": name}) is not None, f"missing {name}"


def test_adds_rss_and_jsonfeed_alternate_links(tmp_path: Path):
    html_file = _write_html(tmp_path)

    enforce_website_spec([html_file], site_url="https://adafede.github.io")

    soup = BeautifulSoup(html_file.read_text(encoding="utf-8"), "html.parser")
    rss_link = soup.find("link", rel="alternate", attrs={"type": "application/rss+xml"})
    assert rss_link is not None
    jf_link = soup.find(
        "link",
        rel="alternate",
        attrs={"type": "application/feed+json"},
    )
    assert jf_link is not None


def test_adds_jsonld_script(tmp_path: Path):
    html_file = _write_html(tmp_path)

    enforce_website_spec([html_file], site_url="https://adafede.github.io")

    soup = BeautifulSoup(html_file.read_text(encoding="utf-8"), "html.parser")
    script = soup.find("script", attrs={"id": "website-spec-jsonld"})
    assert script is not None
    script_type = script.get("type")
    assert script_type is not None
    assert "application/ld+json" in script_type


def test_is_idempotent(tmp_path: Path):
    """Running twice produces no further changes."""
    html_file = _write_html(tmp_path)

    enforce_website_spec([html_file], site_url="https://adafede.github.io")
    first = html_file.read_text(encoding="utf-8")

    enforce_website_spec([html_file], site_url="https://adafede.github.io")
    second = html_file.read_text(encoding="utf-8")

    assert first == second
