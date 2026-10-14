"""Migrate Quarto posts into the Eleventy content tree.

Reads the Quarto project (posts/*.qmd plus the shared entity YAML files under
_includes/entities/) and writes flat Markdown with resolved frontmatter into
src/content/posts/. The Quarto tree is never modified, so both sites can be
built side by side.

Run:  uv run python scripts/site/migrate_posts.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

Metadata = dict[str, Any]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
POSTS_DIR = PROJECT_ROOT / "posts"
TALKS_DIR = PROJECT_ROOT / "talks"
TEACHING_DIR = PROJECT_ROOT / "teaching"
VARIA_DIR = PROJECT_ROOT / "varia"
ARTICLES_DIR = PROJECT_ROOT / "articles"
CV_DIR = PROJECT_ROOT / "cv"
ENTITIES_DIR = PROJECT_ROOT / "_includes" / "entities"
OUT_DIR = PROJECT_ROOT / "src" / "content" / "posts"

# `2026-01-20_chem_flow.qmd` -> id `2026-01-20_chem_flow`
FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})[_-](.+)$")

# Markdown/frontmatter that markdown-it does not understand.
CODE_FENCE_RE = re.compile(r"^```\{[a-zA-Z0-9_]+\}\s*$", re.MULTILINE)
QUARTO_OPTION_RE = re.compile(r"^#\|\s*.*$", re.MULTILINE)
REFS_DIV_RE = re.compile(r"\n:{3,}\s*\{#refs\}\s*:{3,}\s*\n")
NUMBERED_HEADING_RE = re.compile(r"^###\s+References\s*$", re.MULTILINE)

# Content moved from posts/ (depth 1) to src/content/<section>/ (depth 3), so the
# posts' `../images/foo.png` references need one more `../` to keep pointing at
# the repo's images/ directory.
#
# Keeping these as relative paths is deliberate: the static site then
# processes the file, emitting responsive WebP/AVIF with width/height, which is
# what fixes the LCP on post pages. A plain `/images/...` path would be copied
# through raw and blow up the Largest Contentful Paint.
PARENT_PATH_RE = re.compile(r"(?<=[(\"'])\.\./(?=[a-zA-Z0-9_])")

# This script emits optimised
# WebP next to the originals, so a relative path would
# resolve to /images/... and 404. Images are copied verbatim into
# public/images/ instead, and referenced as root-absolute paths that both
# builds serve.
IMAGE_LINK_RE = re.compile(
    r"""(?P<attr>\]\(|src=")(?:\.\./)+(?P<path>images/[^")\s]+)""",
)


def absolutise_images(body: str) -> str:
    """Rewrite `../../../images/x.png` to `/images/x.png`.

    The generated Markdown sits at src/content/<section>/, so a relative image
    path escapes the output tree. public/images/ is served at the site root, so
    a root-absolute path works.
    """
    return IMAGE_LINK_RE.sub(lambda m: f"{m.group('attr')}/{m.group('path')}", body)


def rewrite_paths(body: str, extra_depth: int) -> str:
    """Rebase `../x` references for a file that now sits `extra_depth` levels deeper.

    Depth is counted from the repo root, so posts/ -> src/content/posts/ is +2.
    """
    return (
        PARENT_PATH_RE.sub("../" * extra_depth, body)
        if extra_depth
        else PARENT_PATH_RE.sub("", body)
    )


def load_yaml(path: Path) -> Metadata:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def split_frontmatter(text: str) -> tuple[Metadata, str]:
    if not text.startswith("---"):
        return {}, text
    _, fm, body = text.split("---", 2)
    return yaml.safe_load(fm) or {}, body


def collect_entities() -> tuple[dict[str, Metadata], dict[str, Metadata]]:
    """Merge every author/affiliation entity file into id-keyed maps."""
    authors: dict[str, Metadata] = {}
    affiliations: dict[str, Metadata] = {}

    # Process all entity files in a single pass for efficiency
    for entity_type, key in [("authors", "author"), ("affiliations", "affiliations")]:
        entity_dir = ENTITIES_DIR / entity_type
        target = authors if entity_type == "authors" else affiliations
        for path in sorted(entity_dir.glob("*.yml")):
            for entry in load_yaml(path).get(key) or []:
                if entry.get("id"):
                    # First definition wins; a few ids are declared twice upstream.
                    target.setdefault(entry["id"], entry)

    return authors, affiliations


def resolve_metadata_files(meta: Metadata, base: Path) -> Metadata:
    """Inline Quarto's `metadata-files` keys into the frontmatter mapping."""
    merged: Metadata = {}
    for rel in meta.get("metadata-files") or []:
        path = (base / rel).resolve()
        if not path.exists():
            print(f"  ! missing metadata file: {rel}", file=sys.stderr)
            continue
        for key, value in (load_yaml(path) or {}).items():
            if isinstance(value, list):
                merged.setdefault(key, []).extend(value)
            else:
                merged[key] = value
    return merged


def compact(data: Metadata) -> Metadata:
    """Drop keys whose value is None, so optional fields are absent, not null."""
    return {k: v for k, v in data.items() if v is not None}


def optional_str(value) -> str | None:
    """Drop empty values.

    Several entity files spell an absent identifier as an explicit `null`,
    which PyYAML surfaces either as None or as the string "null". Both mean
    "no value", and both would fail the collection schema.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "~"}:
        return None
    return text


def author_literal(author: Metadata) -> str:
    name = author.get("name") or {}
    if name.get("literal"):
        return str(name["literal"])
    parts = [
        name.get("given", ""),
        name.get("dropping-particle", ""),
        name.get("family", ""),
    ]
    return " ".join(p for p in parts if p).strip() or author.get("id", "Unknown")


def normalize_license(value: Any) -> Metadata | None:
    if not value:
        return None
    if isinstance(value, str):
        # "CC BY" and friends -> link to the canonical deed.
        urls = {
            "CC BY": "https://creativecommons.org/licenses/by/4.0/",
            "CC BY-SA": "https://creativecommons.org/licenses/by-sa/4.0/",
            "CC0": "https://creativecommons.org/publicdomain/zero/1.0/",
            "CC BY-NC": "https://creativecommons.org/licenses/by-nc/4.0/",
        }
        return {"name": value, "url": urls.get(value)}
    if isinstance(value, dict):
        out = {"name": str(value.get("name", ""))}
        if value.get("url"):
            out["url"] = str(value["url"])
        return out
    return None


# Quarto's raw-HTML blocks:
#
#   ```{=html}
#   <iframe width="100%" ... src="https://qlever.scholia.wiki/work/{{< meta qid >}}" ...>
#   </iframe>
#   ```
#
# The article pages already render a proper QLeverEmbed, so these are dropped
# outright. Left in place they became a syntax-highlighted code block, because
# the `{{< meta qid >}}` shortcode has no meaning here and the fence looked like
# a literal code block rather than raw HTML.
# Quarto's Pandoc bracket-attribute span syntax:
#
#   [Adriano Rutz]{about="wd:Q97455964" property="wdt:P31" typeof="schema:Person"}
#
# Neither Markdown parser here understands it, so it printed literally in the
# CV bio. The RDFa attributes are meaningful and kept; only the brackets are
# converted.
SPAN_ATTRS_RE = re.compile(r"\[(?P<text>[^\[\]]+)\]\{(?P<attrs>[^{}]*)\}", re.DOTALL)


def _attrs_to_html(raw: str) -> str:
    """`about="wd:Q1" typeof="schema:Person"` -> ` about="wd:Q1" typeof="..."`."""
    out = []
    for key, value in re.findall(r'([a-zA-Z-]+)="([^"]*)"', raw):
        out.append(f'{key}="{value}"')
    return (" " + " ".join(out)) if out else ""


def convert_span_attributes(body: str) -> str:
    def replace(match: re.Match[str]) -> str:
        text = match.group("text")
        attrs = _attrs_to_html(match.group("attrs"))
        # Escaped emphasis around the span (*text*) is unwrapped here because
        # the asterisks would otherwise end up inside it.
        inner = text.strip()
        if inner.startswith("*") and inner.endswith("*") and len(inner) > 2:
            inner = inner[1:-1]
        return f"<span{attrs}>{inner}</span>" if attrs else inner

    return SPAN_ATTRS_RE.sub(replace, body)


QUARTO_RAW_BLOCK_RE = re.compile(
    r"^```\{=html\}\s*$\n(?P<body>.*?)^```\s*$",
    re.MULTILINE | re.DOTALL,
)
QUARTO_IFRAME_RE = re.compile(r"<iframe\b.*?</iframe>", re.DOTALL | re.IGNORECASE)


def strip_quarto_raw_html(body: str) -> str:
    """Remove Quarto raw-HTML blocks and any bare iframe left in the body."""
    body = QUARTO_RAW_BLOCK_RE.sub("", body)
    return QUARTO_IFRAME_RE.sub("", body)


def convert_body(body: str, extra_depth: int = 0) -> str:
    """Rewrite Quarto/Pandoc-isms into plain Markdown.

    `extra_depth` rebases `../`-relative references; see rewrite_paths().
    """
    body = REFS_DIV_RE.sub("\n", body)
    body = NUMBERED_HEADING_RE.sub("## References", body)
    # ```{r} -> ``` ; drop Quarto cell options (#| label: ...)
    body = CODE_FENCE_RE.sub("```", body)
    body = QUARTO_OPTION_RE.sub("", body)
    body = convert_span_attributes(body)
    body = strip_quarto_raw_html(body)
    body = rewrite_paths(body, extra_depth)
    body = absolutise_images(body)
    return body.strip() + "\n"


def pdf_available(slug: str) -> bool:
    """True when Quarto has already rendered this post's PDF.

    Quarto emits `format-links: [pdf]` for every post, writing the file to
    _site/posts/<id>.pdf. The Eleventy build does not render PDFs (it has no
    equivalent of pandoc + LaTeX in the content pipeline), so the frontmatter
    only advertises the link when the Quarto artifact is actually there.
    """
    return (PROJECT_ROOT / "_site" / "posts" / f"{slug}.pdf").exists()


def build_frontmatter(
    meta: Metadata,
    slug: str,
    date_hint: str | None,
    pdf_slug: str | None = None,
) -> Metadata:
    authors_meta = meta.get("author") or []
    if isinstance(authors_meta, dict):
        authors_meta = [authors_meta]

    authors = []
    for entry in authors_meta:
        if not isinstance(entry, dict):
            continue
        authors.append(
            compact(
                {
                    "name": author_literal(entry),
                    "orcid": optional_str(entry.get("orcid")),
                    "qid": optional_str(entry.get("qid")),
                    "affiliationIds": [
                        a["ref"]
                        for a in entry.get("affiliations") or []
                        if a.get("ref")
                    ],
                },
            ),
        )

    affiliations_meta = meta.get("affiliations") or []
    if isinstance(affiliations_meta, dict):
        affiliations_meta = [affiliations_meta]
    affiliations = [
        compact(
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "ror": optional_str(a.get("ror")),
                "qid": optional_str(a.get("qid")),
            },
        )
        for a in affiliations_meta
        if isinstance(a, dict) and a.get("id")
    ]

    date_value = meta.get("date") or date_hint

    out = {
        "title": meta.get("title") or str(slug or "").replace("_", " ").title(),
        "pubDate": date_value,
        "tags": list(meta.get("categories") or []),
        "authors": authors,
        "affiliations": affiliations,
        "rdfaType": meta.get("rdfaType") or "BlogPosting",
    }

    if meta.get("description"):
        out["description"] = str(meta["description"])
    license_obj = normalize_license(meta.get("license") or meta.get("creative_commons"))
    if license_obj:
        out["license"] = license_obj
    doi_value = normalize_doi(meta.get("doi"))
    if doi_value:
        out["doi"] = doi_value
    if meta.get("updated"):
        out["updatedDate"] = meta["updated"]
    if meta.get("image"):
        out["image"] = str(meta["image"])
    if meta.get("draft"):
        out["draft"] = True

    # The source's `comments` block is not carried across. It was flattened into
    # giscusRepo/hypothesis here, which is not valid Quarto front matter, and
    # Quarto renders these generated files as part of the project — so
    # `quarto render` failed on them with "property name giscusRepo is invalid".
    # The only thing still reading it was the link to the GitHub discussion,
    # which now comes from a single site-level setting (site.discussionsRepo)
    # instead of being repeated per post.

    # Only advertise a PDF when the Quarto build has actually produced one.
    # pdf_slug is the Quarto output name, e.g. "2026-01-20_chem_flow".
    if pdf_slug and pdf_available(pdf_slug):
        # The Quarto URL, not a re-homed one: see stage-public.mjs.
        out["pdf"] = f"/posts/{pdf_slug}.pdf"

    # Return the .bib path relative to the generated file.
    bib = Path("posts") / "references.bib"
    if bib.exists():
        out["bibliography"] = "../../../posts/references.bib"

    return {k: v for k, v in out.items() if v not in (None, [], {}, "") or k == "tags"}


def dump_frontmatter(data: Metadata) -> str:
    # PyYAML output is already valid YAML; do not post-process the quotes.
    dumped = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)
    return f"---\n{dumped}---\n\n"


# ---------------------------------------------------------------------------
# Other sections
#
# talks/ and teaching/ share the posts' shape (title/venue/date/location) but are
# listing entries rather than prose, so they get their own frontmatter builder.
# varia/ entries are link cards with no date in the filename.
# ---------------------------------------------------------------------------


def build_event_frontmatter(
    meta: Metadata,
    date_hint: str | None,
    kind: str,
) -> Metadata:
    out: Metadata = {
        "title": meta.get("title"),
        "date": meta.get("date") or date_hint,
        "venue": meta.get("venue"),
        "location": meta.get("location"),
        "tags": list(meta.get("categories") or [kind]),
    }
    # Talks and courses declare their speaker through `metadata-files`, the same
    # way articles do. Without this the rendered pages had no author at all, even
    # though the Quarto sources carry one.
    authors = normalize_authors(meta)
    if authors:
        out["authors"] = authors
        affil_ids = [a for author in authors for a in author.get("affiliationIds", [])]
        if affil_ids:
            out["affiliationIds"] = list(dict.fromkeys(affil_ids))
    if meta.get("description"):
        out["description"] = str(meta["description"]).strip()
    if meta.get("url"):
        out["url"] = str(meta["url"])
    doi_value = normalize_doi(meta.get("doi"))
    if doi_value:
        out["doi"] = doi_value
    if meta.get("image"):
        out["image"] = str(meta["image"])
    return {k: v for k, v in out.items() if v not in (None, [], {}, "") or k == "tags"}


def build_card_frontmatter(meta: Metadata) -> Metadata:
    out: Metadata = {
        # Varia titles are written with emphasis markers ("**CASCADE**: ...") and
        # rendered as plain strings, so the Markdown has to come off here.
        "title": strip_inline_markdown(str(meta.get("title") or "")),
        "url": meta.get("url"),
        "tags": list(meta.get("categories") or []),
    }
    if meta.get("description"):
        out["description"] = strip_inline_markdown(str(meta["description"]).strip())
    if meta.get("image"):
        out["image"] = str(meta["image"])
    if meta.get("image-alt"):
        out["imageAlt"] = str(meta["image-alt"])
    return {k: v for k, v in out.items() if v not in (None, [], {}, "") or k == "tags"}


def write(target: Path, frontmatter: Metadata, body: str, extra_depth: int = 0) -> None:
    """Write a generated content file.

    `extra_depth` is how many directory levels deeper the target sits compared
    to the Quarto source, so `../`-relative paths keep resolving.
    """
    target.write_text(
        dump_frontmatter(frontmatter) + convert_body(body, extra_depth),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Articles
#
# articles.qmd drives five Quarto listings. `first` and `shared` render as
# card grids, `co` and `thesis` as tables, and the commented-out `last` listing
# is intentionally not ported (no articles/last/ directory exists).
# ---------------------------------------------------------------------------

ARTICLE_GROUPS = {
    "first": ("articles/first", "Single first author"),
    "shared": ("articles/shared", "Shared first author"),
    "co": ("articles/co", "Co-author"),
}


def build_article_frontmatter(
    meta: Metadata,
    group: str,
    date_hint: str | None,
) -> Metadata:
    authors = normalize_authors(meta)
    out: Metadata = {
        "title": strip_inline_markdown(
            str(meta.get("title") or "").replace("\n  ", " "),
        ),
        "group": group,
        "venue": strip_inline_markdown(str(meta["venue"]))
        if meta.get("venue")
        else None,
        "date": meta.get("date") or date_hint,
        "doi": normalize_doi(meta.get("doi")),
        "qid": optional_str(meta.get("qid")),
        "url": normalize_url(meta.get("url")),
        "tags": list(meta.get("categories") or []),
        "authors": authors,
        # Emphasis and links are kept: the abstract is rendered as Markdown,
        # so stripping them here would lose the species names and URLs the
        # authors italicised and linked in the source.
        "abstract": clean_abstract(meta.get("abstract")) or None,
    }
    if meta.get("image"):
        out["image"] = str(meta["image"])
    if meta.get("image-alt"):
        out["imageAlt"] = str(meta["image-alt"])
    return {k: v for k, v in out.items() if v not in (None, [], {}, "") or k == "tags"}


def normalize_url(value) -> str | None:
    """Quarto wraps bare URLs in angle brackets: `<https://doi.org/10.x>`."""
    if not value:
        return None
    return str(value).strip().strip("<>").strip()


def normalize_doi(value) -> str | None:
    """Accept `10.x/y` or a full resolver URL and store the bare DOI.

    talks/2023-07-03_GA.qmd carries `https://doi.org/10.1055/...`, which the
    articles schema rejects. Normalising here keeps the schema strict instead of
    loosening it to `z.string()`.
    """
    if not value:
        return None
    text = str(value).strip().strip("<>")
    text = re.sub(r"^(?:https?://)?(?:dx\.)?doi\.org/", "", text, flags=re.IGNORECASE)
    return text.strip() or None


def strip_inline_markdown(text: str) -> str:
    """Remove inline Markdown emphasis from a title or venue.

    Titles in the Quarto sources carry Markdown: "*Swertia chirayita*",
    "**SAPID**", "MultiMS^2^". Quarto rendered it; a plain string or an <h1>
    shows it literally, so the markup is dropped and only the text kept.

    Each pattern is anchored so ordinary punctuation survives: "*μ*M" is
    emphasis, but "5 ± 1.6 μM" and a bare "^" in prose are left alone.
    """
    value = text
    # Bold first (**x** before *x*, so the pairs do not fight).
    value = re.sub(r"\*\*([^*]+)\*\*", r"\1", value)
    # Italic: an asterisk hugging a non-word character on one side, or wrapping
    # a word on both. That excludes "μM" style unit usage like "*μ*M".
    value = re.sub(r"(?<![\w*])\*([^*\s][^*]*?)\*", r"\1", value)
    value = re.sub(r"\*([^*\s][^*]*?)\*(?![\w*])", r"\1", value)
    # Superscript: digits only, so "MultiMS^2^" loses the carets.
    value = re.sub(r"\^(\d+(?:\^\d+)*)\^", r"\1", value)
    # Link syntax in titles, e.g. "[LOTUS](https://x)" -> "LOTUS".
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    # Pandoc autolinks: <https://example.org>. Neither Markdown parser here
    # treats bare angle brackets as an autolink, so they printed literally in
    # the varia descriptions.
    value = re.sub(r"<((?:https?://|mailto:)[^>\s]+)>", r"\1", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def clean_abstract(value) -> str | None:
    """Fold a block-scalar abstract (`>` / `|`) into one paragraph."""
    if not value:
        return None
    return " ".join(str(value).split())


def normalize_authors(meta: Metadata) -> list[Metadata]:
    """Same entity shape as posts, plus the co-author fields the articles use."""
    raw = meta.get("author") or []
    if isinstance(raw, dict):
        raw = [raw]
    out = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        item = compact(
            {
                "name": author_literal(entry),
                # Zod's .optional() rejects an explicit null, so empty
                # identifiers have to be omitted rather than set to None.
                "orcid": optional_str(entry.get("orcid")),
                "qid": optional_str(entry.get("qid")),
                "affiliationIds": [
                    a["ref"] for a in entry.get("affiliations") or [] if a.get("ref")
                ],
            },
        )
        # The entity files use several spellings for these flags; normalise.
        if entry.get("correspondence") or entry.get("corresponding"):
            item["corresponding"] = True
        if entry.get("equal-contributor") or entry.get("equalContributor"):
            item["equalContributor"] = True
        out.append(item)
    return out


def migrate_articles(clean: bool, affils_all: Metadata) -> int:
    written = 0
    out_root = PROJECT_ROOT / "src" / "content" / "articles"
    out_root.mkdir(parents=True, exist_ok=True)

    for group, (rel, _label) in ARTICLE_GROUPS.items():
        source_dir = PROJECT_ROOT / rel
        out_dir = out_root / group
        out_dir.mkdir(parents=True, exist_ok=True)

        for source in sorted(source_dir.glob("*.qmd")):
            meta, body = split_frontmatter(source.read_text(encoding="utf-8"))
            meta = {**resolve_metadata_files(meta, source_dir), **meta}
            match = FILENAME_RE.match(source.stem)
            date_hint = match.group(1) if match else None

            target = out_dir / f"{source.stem}.md"
            if clean and target.exists():
                target.unlink()
                continue
            write(
                target,
                build_article_frontmatter(meta, group, date_hint),
                body,
                extra_depth=4,
            )
            print(f"  + {target.relative_to(PROJECT_ROOT)}")
            written += 1

    # The thesis is a single file, not a listing directory.
    thesis = ARTICLES_DIR / "thesis.qmd"
    if thesis.exists():
        meta, body = split_frontmatter(thesis.read_text(encoding="utf-8"))
        meta = {**resolve_metadata_files(meta, ARTICLES_DIR), **meta}
        out_dir = out_root / "thesis"
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / "thesis.md"
        if not clean:
            write(
                target,
                build_article_frontmatter(meta, "thesis", meta.get("date")),
                body,
                extra_depth=4,
            )
            print(f"  + {target.relative_to(PROJECT_ROOT)}")
            written += 1
        elif target.exists():
            target.unlink()

    # Affiliation registry, so article pages can resolve an author's
    # affiliationIds to a display name and to link it. Quarto resolved these at
    # render time from the same entity files, which is where ror/qid come from.
    registry = [
        {
            "id": aid,
            "name": entry.get("name"),
            "ror": entry.get("ror"),
            "qid": entry.get("qid"),
        }
        for aid, entry in sorted(affils_all.items())
        if entry.get("name")
    ]
    registry_target = PROJECT_ROOT / "src" / "content" / "affiliations.json"
    if not clean:
        registry_target.write_text(
            json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"  + {registry_target.relative_to(PROJECT_ROOT)}")
        written += 1

    # Publication profiles (Scholia / ORCID / Google Scholar).
    profiles = ARTICLES_DIR / "profiles.qmd"
    if profiles.exists():
        meta, _ = split_frontmatter(profiles.read_text(encoding="utf-8"))
        target = out_root.parent / "profiles.json"
        payload = {
            "qid": meta.get("qid"),
            "orcid": meta.get("orcid"),
            "scholar": meta.get("scholar"),
        }
        if not clean:
            target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            print(f"  + {target.relative_to(PROJECT_ROOT)}")
            written += 1

    return written


# ---------------------------------------------------------------------------
# CV
#
# cv.qmd is five section includes, each pulling in per-entry partials named
# `_{YEAR}_{ORG}.qmd`. The partials are plain Markdown (a `###` heading plus a
# body, or a bullet list for awards) with no frontmatter, so the year-range and
# heading text are parsed out of the Markdown itself.
# ---------------------------------------------------------------------------

CV_SECTIONS = [
    ("experience", "Professional Experience", "Professional Experience"),
    ("education", "Education", "Education"),
    ("awards", "Awards", "Awards"),
    ("sports", "Sports", "Sports"),
]

# "### Postdoctoral Researcher, ETH Zürich, Zürich (2022 - present)"
CV_HEADING_RE = re.compile(r"^###\s+(?P<title>.+?)(?:\s*\((?P<range>[^)]*)\))?\s*$")


def parse_cv_entry(path: Path) -> Metadata | None:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return None

    match = (
        CV_HEADING_RE.match(text.splitlines()[0]) if text.startswith("###") else None
    )
    if match:
        title = match.group("title").strip()
        date_range = (match.group("range") or "").strip()
        body = text.split("\n", 1)[1].strip() if "\n" in text else ""
        kind = "heading"
    else:
        # Awards and sports entries alternate bullet list / heading styles.
        title = ""
        date_range = ""
        body = text
        kind = "bullets"

    year_match = re.match(
        r"(?P<from>\d{4})\s*(?:-|–|—)\s*(?P<to>present|\d{4})",
        date_range,
    )
    start = int(year_match.group("from")) if year_match else None
    end = year_match.group("to") if year_match else None

    # Fall back to the filename year so ordering works even without a heading.
    file_year = re.match(r"_(\d{4})_", path.name)
    if start is None and file_year:
        start = int(file_year.group(1))

    cleaned = clean_abstract(body) if kind == "heading" else None

    return {
        "title": title,
        "summary": inline_md(cleaned) if cleaned else None,
        "bullets": clean_cv_bullets(body) if kind == "bullets" else None,
        "startYear": start,
        "endYear": None if end in (None, "present") else int(end) if end else None,
        "current": end == "present",
        "order": file_year.group(1) if file_year else "9999",
    }


def clean_cv_bullets(body: str) -> list[Metadata]:
    """Join wrapped bullet lines into one string per bullet.

    The CV partials wrap Markdown across lines, so a naive per-line scan would
    truncate each award at the first line break.

    Inline Markdown is converted to HTML here rather than at render time: the
    CV partials only ever use emphasis and links, and turning them into markup
    keeps the CV template free of a Markdown renderer.
    """
    bullets: list[str] = []
    current: list[str] = []

    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            if current:
                bullets.append(" ".join(" ".join(current).split()))
            current = [stripped[2:]]
        elif stripped and current:
            # Continuation of the bullet above.
            current.append(stripped)

    if current:
        bullets.append(" ".join(" ".join(current).split()))

    # Turn the bold lead-in into a separate label field.
    out = []
    for text in bullets:
        lead = re.match(r"\*\*(.+?)\*\*\s*:?\s*(.*)$", text, re.DOTALL)
        if lead:
            out.append(
                {
                    "label": lead.group(1).strip(),
                    "detail": inline_md(lead.group(2).strip()),
                },
            )
        else:
            out.append({"label": None, "detail": inline_md(text)})
    return out


def inline_md(text: str) -> str:
    """Convert the inline Markdown the CV uses into HTML.

    Handles `[label](url)`, `<url>` autolinks, and `*emphasis*`. Everything is
    HTML-escaped first, so the result is safe to emit with set:html.
    """
    import html as html_mod

    escaped = html_mod.escape(text, quote=False)

    # [label](url) — the label may itself contain escaped entities.
    escaped = re.sub(
        r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
        r'<a href="\2">\1</a>',
        escaped,
    )
    # <https://...> autolink; the angle brackets survive escaping.
    escaped = re.sub(
        r"&lt;(https?://[^\s&]+)&gt;",
        r'<a href="\1">\1</a>',
        escaped,
    )
    # *emphasis* and **strong**, innermost first.
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", escaped)
    return escaped.strip()


def migrate_cv(clean: bool) -> int:
    written = 0
    target_dir = PROJECT_ROOT / "src" / "content" / "cv"
    target_dir.mkdir(parents=True, exist_ok=True)

    for folder, key, label in CV_SECTIONS:
        source_dir = CV_DIR / folder
        if not source_dir.exists():
            continue
        entries = [parse_cv_entry(p) for p in sorted(source_dir.glob("*.qmd"))]
        entries = [e for e in entries if e]

        target = target_dir / f"{folder}.json"
        if clean:
            if target.exists():
                target.unlink()
            continue

        target.write_text(
            json.dumps(
                {"label": label, "entries": entries},
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"  + {target.relative_to(PROJECT_ROOT)}")
        written += 1

    # The bio is prose with RDFa links; keep it as Markdown. The leading
    # "## Bio" heading is dropped because the CV template renders its own <h2>.
    bio = CV_DIR / "_bio.qmd"
    if bio.exists():
        target = target_dir / "bio.md"
        if clean:
            if target.exists():
                target.unlink()
        else:
            _, body = split_frontmatter(bio.read_text(encoding="utf-8"))
            body = re.sub(r"^##\s+Bio\s*\n", "", body.lstrip())
            target.write_text(convert_body(body, extra_depth=3), encoding="utf-8")
            print(f"  + {target.relative_to(PROJECT_ROOT)}")
            written += 1

    # cv.qmd's cvmeta block drives the header strip.
    cv_meta_source = PROJECT_ROOT / "cv.qmd"
    if cv_meta_source.exists():
        meta, _ = split_frontmatter(cv_meta_source.read_text(encoding="utf-8"))
        target = target_dir / "meta.json"
        if clean:
            if target.exists():
                target.unlink()
        else:
            payload = {
                "profession": meta.get("cvprofession"),
                "footer": meta.get("cvfooter") or {},
                "meta": meta.get("cvmeta") or [],
                # Named contact fields. Kept apart from cvmeta because that block
                # is a contract with cv/template.tex, which prints its free-text
                # `right` values into the PDF; the website wants labelled fields
                # it does not have to pull apart.
                "contact": {
                    # Only the fields the website publishes. `phone` and
                    # `website` exist in cv.qmd for the PDF template and are
                    # deliberately not carried over to the web.
                    "email": (meta.get("cvcontact") or {}).get("email"),
                    "location": (meta.get("cvcontact") or {}).get("location"),
                },
            }
            target.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(f"  + {target.relative_to(PROJECT_ROOT)}")
            written += 1

    return written


def migrate(clean: bool = False) -> int:
    authors_all, affils_all = collect_entities()
    written = 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- posts ---
    for source in sorted(POSTS_DIR.glob("*.qmd")):
        match = FILENAME_RE.match(source.stem)
        if not match:
            print(f"  - skipping {source.name} (no date prefix)")
            continue
        date_hint, slug = match.groups()

        text = source.read_text(encoding="utf-8")
        meta, body = split_frontmatter(text)
        meta = {**resolve_metadata_files(meta, POSTS_DIR), **meta}

        # Backfill authors/affiliations from the entity registry when the file
        # referenced none (all current posts do, but this keeps the script general).
        if not meta.get("author") and meta.get("authors_for_feed"):
            meta.setdefault("author", meta["authors_for_feed"])

        target = OUT_DIR / f"{date_hint}_{slug}.md"
        if clean and target.exists():
            target.unlink()
            continue
        write(
            target,
            build_frontmatter(meta, slug, date_hint, pdf_slug=f"{date_hint}_{slug}"),
            body,
            extra_depth=3,
        )
        print(f"  + {target.relative_to(PROJECT_ROOT)}")
        written += 1

    # --- talks and teaching ---
    for source_dir, kind in ((TALKS_DIR, "Talk"), (TEACHING_DIR, "Teaching")):
        out_dir = PROJECT_ROOT / "src" / "content" / source_dir.name
        out_dir.mkdir(parents=True, exist_ok=True)
        for source in sorted(source_dir.glob("*.qmd")):
            meta, body = split_frontmatter(source.read_text(encoding="utf-8"))
            meta = {**resolve_metadata_files(meta, source_dir), **meta}
            match = FILENAME_RE.match(source.stem)
            date_hint = match.group(1) if match else None
            target = out_dir / f"{source.stem}.md"
            if clean and target.exists():
                target.unlink()
                continue
            write(
                target,
                build_event_frontmatter(meta, date_hint, kind),
                body,
                extra_depth=3,
            )
            print(f"  + {target.relative_to(PROJECT_ROOT)}")
            written += 1

    # --- varia (link cards, no date in filename) ---
    for source in sorted(VARIA_DIR.rglob("*.qmd")):
        if source.name.startswith("_"):
            continue
        meta, body = split_frontmatter(source.read_text(encoding="utf-8"))
        group = source.parent.name
        frontmatter = build_card_frontmatter(meta)
        frontmatter["group"] = group
        target = (
            PROJECT_ROOT / "src" / "content" / "varia" / group / f"{source.stem}.md"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        if clean and target.exists():
            target.unlink()
            continue
        write(target, frontmatter, body, extra_depth=3)
        print(f"  + {target.relative_to(PROJECT_ROOT)}")
        written += 1

    written += migrate_articles(clean, affils_all)
    written += migrate_cv(clean)

    # Sanity report on the entity registry, useful when frontmatter looks thin.
    print(f"\n{len(authors_all)} authors, {len(affils_all)} affiliations in registry")
    print(f"{written} file(s) migrated into src/content/")
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--clean",
        action="store_true",
        help="remove generated files and exit",
    )
    args = parser.parse_args()
    print("Migrating Quarto content -> Eleventy content tree")
    migrate(clean=args.clean)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
