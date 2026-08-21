"""Characterization tests for the RSS feed pipeline.

Covers the three live utility functions that postrender.py chains together:
inject_doi_in_rss, inject_cito_annotations_in_rss, and convert_rss_to_json_feed.
"""

import json
from pathlib import Path

from scripts.infrastructure import YamlLoader
from scripts.utilities.convert_rss_to_json_feed import convert_rss_to_json_feed
from scripts.utilities.inject_cito_annotations_in_rss import (
    inject_cito_annotations_in_rss,
)
from scripts.utilities.inject_doi_in_rss import inject_doi_in_rss

# ---------------------------------------------------------------------------
# Test fixtures / helpers
# ---------------------------------------------------------------------------

SAMPLE_RSS = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Adriano Rutz</title>
    <description>Personal website</description>
    <link>https://adafede.github.io</link>
    <language>en</language>
    <atom:link href="https://adafede.github.io/rss.xml" rel="self"/>
    <item>
      <title>First Post</title>
      <link>https://adafede.github.io/posts/2025-01-01_first.html</link>
      <description><![CDATA[
        <div id="refs">
          <div id="ref-smith2020" class="csl-entry">Smith citation.</div>
        </div>
      ]]></description>
    </item>
  </channel>
</rss>
"""


def _qmd_file(tmp_path: Path, name: str, title: str, doi: str | None = None) -> Path:
    frontmatter = f"title: {title}\ndate: 2025-01-01\n"
    if doi:
        frontmatter += f"doi: {doi}\n"
    qmd = tmp_path / name
    qmd.write_text(f"---\n{frontmatter}---\n\nBody.\n", encoding="utf-8")
    return qmd


# ---------------------------------------------------------------------------
# inject_doi_in_rss
# ---------------------------------------------------------------------------


def test_inject_doi_adds_doi_tag(tmp_path: Path):
    rss = tmp_path / "rss.xml"
    rss.write_text(SAMPLE_RSS, encoding="utf-8")
    qmd1 = _qmd_file(tmp_path, "2025-01-01_first.qmd", "First Post", "10.59350/abc123")

    inject_doi_in_rss(rss, [qmd1])

    content = rss.read_text(encoding="utf-8")
    assert "<doi>https://doi.org/10.59350/abc123</doi>" in content


def test_inject_doi_no_op_when_doi_already_present(tmp_path: Path):
    rss = tmp_path / "rss.xml"
    rss_text = SAMPLE_RSS.replace(
        "</item>",
        "<doi>https://doi.org/10.59350/existing</doi>\n</item>",
    )
    rss.write_text(rss_text, encoding="utf-8")
    qmd1 = _qmd_file(tmp_path, "2025-01-01_first.qmd", "First Post", "10.59350/abc123")

    inject_doi_in_rss(rss, [qmd1])

    content = rss.read_text(encoding="utf-8")
    assert "<doi>https://doi.org/10.59350/existing</doi>" in content
    assert "abc123" not in content


def test_inject_doi_skips_unmatched_titles(tmp_path: Path):
    rss = tmp_path / "rss.xml"
    rss.write_text(SAMPLE_RSS, encoding="utf-8")
    _qmd_file(tmp_path, "2025-01-01_other.qmd", "Unrelated Post", "10.59350/xyz")

    inject_doi_in_rss(rss, [tmp_path / "2025-01-01_other.qmd"])

    content = rss.read_text(encoding="utf-8")
    assert "<doi>" not in content  # the item title "First Post" was not matched


# ---------------------------------------------------------------------------
# inject_cito_annotations_in_rss
# ---------------------------------------------------------------------------


def test_inject_cito_annotates_matching_citation(tmp_path: Path):
    rss = tmp_path / "rss.xml"
    rss.write_text(SAMPLE_RSS, encoding="utf-8")

    inject_cito_annotations_in_rss(rss, {"smith2020": ["cites_as_evidence"]})

    content = rss.read_text(encoding="utf-8")
    assert "[cito:citesAsEvidence]" in content


def test_inject_cito_skips_unmatched_citations(tmp_path: Path):
    rss = tmp_path / "rss.xml"
    rss.write_text(SAMPLE_RSS, encoding="utf-8")

    inject_cito_annotations_in_rss(rss, {"other2021": ["cites"]})

    content = rss.read_text(encoding="utf-8")
    assert "cito:" not in content


def test_inject_cito_is_idempotent(tmp_path: Path):
    rss = tmp_path / "rss.xml"
    rss_text = SAMPLE_RSS.replace(
        "Smith citation.</div>",
        'Smith citation.<span class="cito"> [cito:cites]</span></div>',
    )
    rss.write_text(rss_text, encoding="utf-8")

    inject_cito_annotations_in_rss(rss, {"smith2020": ["cites"]})

    content = rss.read_text(encoding="utf-8")
    assert content.count("cito:cites") == 1


# ---------------------------------------------------------------------------
# convert_rss_to_json_feed
# ---------------------------------------------------------------------------


def test_convert_rss_to_json_feed_basic(tmp_path: Path):
    rss = tmp_path / "rss.xml"
    rss.write_text(SAMPLE_RSS, encoding="utf-8")
    json_path = tmp_path / "feed.json"

    convert_rss_to_json_feed(rss, json_path)

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["version"] == "https://jsonfeed.org/version/1.1"
    assert data["title"] == "Adriano Rutz"
    assert data["description"] == "Personal website"
    assert data["home_page_url"] == "https://adafede.github.io"
    assert (
        data["feed_url"] == "https://adafede.github.io/rss.json"
    )  # .xml→.json per extract_feed_metadata line 116
    assert data["language"] == "en"
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "First Post"
    assert "https://doi.org" not in str(data)  # no DOIs injected yet


def test_convert_after_doi_injection(tmp_path: Path):
    """End-to-end: inject DOI then convert — JSON Feed item gets the guid/id."""
    rss = tmp_path / "rss.xml"
    rss.write_text(SAMPLE_RSS, encoding="utf-8")
    qmd1 = _qmd_file(tmp_path, "2025-01-01_first.qmd", "First Post", "10.59350/abc123")

    yaml_loader = YamlLoader()
    inject_doi_in_rss(rss, [qmd1], yaml_loader=yaml_loader)
    convert_rss_to_json_feed(rss, tmp_path / "feed.json")

    data = json.loads((tmp_path / "feed.json").read_text(encoding="utf-8"))
    item = data["items"][0]
    # inject_doi_in_rss writes <doi> tag (not <guid>), so it won't appear as item id
    assert item["title"] == "First Post"
