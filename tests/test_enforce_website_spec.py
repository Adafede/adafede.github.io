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
    _ = path.write_text(SAMPLE_HTML, encoding="utf-8")
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


def test_the_indexed_upserts_match_the_whole_document_scan():
    """`_upsert_link`/`_upsert_meta` gained an optional index.

    The index is an optimisation, and an optimisation that changes *which* node
    is updated — or that stops finding the node the scan would have found —
    would duplicate a tag or rewrite the wrong one. Both paths must be the same
    function.
    """
    from scripts.utilities.enforce_website_spec import (
        _link_index,
        _meta_index,
        _upsert_link,
        _upsert_meta,
    )

    soup_html = """<!DOCTYPE html>
<html lang="en"><head>
  <link rel="preload dns-prefetch" href="https://example.test/a.css">
  <link rel="canonical" href="https://stale.example/old">
  <meta name="description" content="stale">
  <meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)">
</head><body><p>x</p></body></html>
"""

    def run(use_index: bool) -> str:
        soup = BeautifulSoup(soup_html, "html.parser")
        links = _link_index(soup) if use_index else None
        metas = _meta_index(soup) if use_index else None

        _upsert_link(
            soup,
            rel="canonical",
            href="https://adafede.github.io/page.html",
            index=links,
        )
        _upsert_link(
            soup,
            rel="preconnect",
            href="https://example.test/a.css",
            index=links,
        )
        _upsert_meta(
            soup,
            attr_name="name",
            attr_value="description",
            content="Fresh",
            index=metas,
        )
        _upsert_meta(
            soup,
            attr_name="name",
            attr_value="theme-color",
            content="#000000",
            index=metas,
            media="(prefers-color-scheme: light)",
        )
        return str(soup)

    assert run(use_index=True) == run(use_index=False)


def test_a_link_reachable_under_two_rel_tokens_is_reused():
    """The scan and the index must both find a tag carrying multiple rel tokens.

    `<link rel="preload dns-prefetch">` is a preconnect and a dns-prefetch, so
    upserting either token reuses it rather than adding a second copy of the
    same href.
    """
    from scripts.utilities.enforce_website_spec import _link_index, _upsert_link

    soup = BeautifulSoup(
        "<html><head>"
        '<link rel="preconnect dns-prefetch" href="https://www.wikidata.org">'
        "</head><body></body></html>",
        "html.parser",
    )
    links = _link_index(soup)

    assert (
        _upsert_link(
            soup,
            rel="dns-prefetch",
            href="https://www.wikidata.org",
            index=links,
        )
        is False
    )
    assert (
        _upsert_link(
            soup,
            rel="preconnect",
            href="https://www.wikidata.org",
            index=links,
        )
        is False
    )

    wikidata = soup.find_all("link", href="https://www.wikidata.org")
    assert len(wikidata) == 1
    assert set(wikidata[0]["rel"]) == {"dns-prefetch", "preconnect"}


def test_does_not_add_simpleanalytics_preconnect(tmp_path: Path):
    html_file = _write_html(tmp_path)

    enforce_website_spec([html_file], site_url="https://adafede.github.io")

    raw = html_file.read_text(encoding="utf-8")
    assert "scripts.simpleanalyticscdn.com" not in raw


def test_injects_nojs_analytics_pixel_for_root_and_nested_route(tmp_path: Path):
    root_html = _write_html(tmp_path, "index.html")
    nested_html = _write_html(tmp_path, "posts/demo.html")

    enforce_website_spec([root_html, nested_html], site_url="https://adafede.github.io")

    for html_file, expected_path in [
        (root_html, "%2F"),
        (nested_html, "%2Fposts%2Fdemo.html"),
    ]:
        raw = html_file.read_text(encoding="utf-8")
        expected_src = (
            "https://queue.simpleanalyticscdn.com/noscript.gif"
            f"?hostname=adafede.codeberg.page&amp;path={expected_path}"
        )
        assert f'src="{expected_src}"' in raw
        assert "&amp;amp;" not in raw

        soup = BeautifulSoup(raw, "html.parser")
        pixel = soup.body.find("img", class_="analytics-pixel")
        assert pixel is not None
        assert pixel.find_parent("noscript") is None
        assert pixel.get("alt") == ""
        assert pixel.get("width") == "1"
        assert pixel.get("height") == "1"
        assert pixel.get("referrerpolicy") == "no-referrer-when-downgrade"
        assert pixel.get("decoding") == "async"
        assert pixel.get("fetchpriority") == "low"
        assert pixel.get("aria-hidden") == "true"
        assert "loading" not in pixel.attrs
        assert "crossorigin" not in pixel.attrs


def test_strips_legacy_simpleanalytics_script_and_noscript_pixel(tmp_path: Path):
    site = tmp_path / "_site"
    html_file = site / "about.html"
    html_file.parent.mkdir(parents=True, exist_ok=True)
    _ = html_file.write_text(
        """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>About</title>
  <script async defer src="https://scripts.simpleanalyticscdn.com/latest.js"></script>
</head>
<body>
  <p>Hello</p>
  <noscript><img src="https://queue.simpleanalyticscdn.com/noscript.gif" alt=""></noscript>
</body>
</html>
""",
        encoding="utf-8",
    )

    enforce_website_spec([html_file], site_url="https://adafede.github.io")

    raw = html_file.read_text(encoding="utf-8")
    assert "scripts.simpleanalyticscdn.com" not in raw
    assert "<noscript>" not in raw
    assert (
        'src="https://queue.simpleanalyticscdn.com/noscript.gif'
        '?hostname=adafede.codeberg.page&amp;path=%2Fabout.html"' in raw
    )
