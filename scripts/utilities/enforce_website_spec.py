"""Website-spec metadata hardening for rendered HTML pages.

Adds missing head tags so generated pages meet modern baseline expectations.
"""

import json
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

from scripts.infrastructure import get_logger

logger = get_logger(__name__)

DEFAULT_DESCRIPTION = (
    "Personal website of Adriano Rutz - Swiss Pharmaceutical Scientist "
    "specializing in metabolomics, mass spectrometry, and natural products research."
)


def _meta_index(soup) -> dict[str, list]:
    """`<meta>` elements grouped by their name/property/itemprop attribute.

    See `_link_index`: `_upsert_meta` is called a dozen times per page.
    """
    index: dict[str, list] = {}
    for node in soup.find_all("meta"):
        for key in ("name", "property", "itemprop"):
            if node.get(key):
                index.setdefault(key, []).append(node)
    return index


def _meta_matching(
    index: dict[str, list],
    attr_name: str,
    attr_value: str,
    extra_attrs: dict[str, object],
):
    """The first meta in the index whose attributes all match, or None."""
    selector = {attr_name: attr_value, **extra_attrs}
    return next(
        (
            node
            for node in index.get(attr_name, [])
            if all(node.get(key) == value for key, value in selector.items())
        ),
        None,
    )


def _upsert_meta(
    soup,
    *,
    attr_name: str,
    attr_value: str,
    content: str,
    index=None,
    **extra_attrs,
) -> bool:
    """Create or update a meta tag and return whether it changed.

    Args:
        soup: The document to modify.
        attr_name: Which attribute identifies the tag (name/property/itemprop).
        attr_value: The value of that attribute.
        content: The content to set.
        index: A `_meta_index` to search instead of the document. Optional, for
            callers that upsert more than one meta tag and can share the index.
        extra_attrs: Further attributes that must already match for the tag to
            be reused rather than duplicated.
    """
    if index is None:
        node = soup.find("meta", attrs={attr_name: attr_value, **extra_attrs})
    else:
        node = _meta_matching(index, attr_name, attr_value, extra_attrs)

    if node is None:
        attrs = {"content": content, attr_name: attr_value, **extra_attrs}
        node = soup.new_tag("meta", attrs=attrs)
        soup.head.append(node)
        if index is not None:
            index.setdefault(attr_name, []).append(node)
        return True

    if node.get("content") != content:
        node["content"] = content
        return True

    changed = False
    for key, value in extra_attrs.items():
        if node.get(key) != value:
            node[key] = value
            changed = True
    return changed


def _link_index(soup) -> dict[str, list]:
    """`<link>` elements grouped by each rel token they carry.

    `_upsert_link` is called about a dozen times per page — four preconnects,
    four DNS prefetches and five or six more — and each call used to rescan the
    whole head for that rel. The index holds the same Tag objects, so matching
    against it mutates the document.
    """
    index: dict[str, list] = {}
    for node in soup.find_all("link"):
        for token in _rel_tokens(node):
            index.setdefault(token, []).append(node)
    return index


def _rel_tokens(node) -> list[str]:
    """The whitespace-separated tokens of a `<link>`'s rel attribute."""
    values = node.get("rel", [])
    return values if isinstance(values, list) else str(values).split()


def _upsert_link(soup, *, rel: str, href: str, index=None, **attrs) -> bool:
    """Create or update a link tag and return whether it changed.

    Args:
        soup: The document to modify.
        rel: The rel token to match.
        href: The href to set.
        index: A `_link_index` to search instead of the head. Optional, for
            callers that upsert more than one link and can share the index.
        attrs: Additional attributes that must already match for the link to be
            reused rather than duplicated.
    """
    candidates = (
        index.get(rel, [])
        if index is not None
        else [node for node in soup.find_all("link") if rel in _rel_tokens(node)]
    )
    node = next(
        (
            candidate
            for candidate in candidates
            if all(candidate.get(key) == value for key, value in attrs.items())
        ),
        None,
    )

    if node is None:
        link_attrs = {"rel": rel, "href": href, **attrs}
        node = soup.new_tag("link", attrs=link_attrs)
        soup.head.append(node)
        if index is not None:
            index.setdefault(rel, []).append(node)
        return True

    changed = False
    if node.get("href") != href:
        node["href"] = href
        changed = True

    for key, value in attrs.items():
        if node.get(key) != value:
            node[key] = value
            changed = True
    return changed


def _route_from_html(html_file: Path, site_dir: Path) -> str:
    rel_path = html_file.relative_to(site_dir).as_posix()
    if rel_path == "index.html":
        return "/"
    if rel_path.endswith("/index.html"):
        return f"/{rel_path[:-10]}/"
    return f"/{rel_path}"


def _canonical_url(site_url: str, route: str) -> str:
    return f"{site_url.rstrip('/')}{route}"


def _description_for_page(soup) -> str:
    meta_description = soup.find("meta", attrs={"name": "description"})
    if meta_description and meta_description.get("content"):
        return meta_description["content"].strip()

    og_description = soup.find("meta", attrs={"property": "og:description"})
    if og_description and og_description.get("content"):
        return og_description["content"].strip()

    return DEFAULT_DESCRIPTION


def _title_for_page(soup) -> str:
    title = soup.find("title")
    if title and title.text:
        return title.text.strip()
    return "Adriano Rutz"


def _inject_jsonld(
    soup,
    *,
    site_url: str,
    canonical_url: str,
    route: str,
    title: str,
    description: str,
    author_name: str | None = None,
    date_published: date | None = None,
    date_modified: date | None = None,
) -> bool:
    """Create or update a JSON-LD structured data tag and return whether it changed."""
    payload = {
        "@context": "https://schema.org",
        "@type": "WebSite" if route == "/" else "WebPage",
        "name": title,
        "url": canonical_url,
        "description": description,
        "inLanguage": (soup.html.get("lang") if soup.html else "en") or "en",
    }

    if route != "/":
        payload["isPartOf"] = {"@type": "WebSite", "url": site_url.rstrip("/") + "/"}

    # Add author and dates for article pages
    if route.startswith(("/posts/", "/articles/")):
        payload["@type"] = "Article"
        if author_name:
            payload["author"] = {"@type": "Person", "name": author_name}
        if date_published:
            payload["datePublished"] = date_published.isoformat()
        if date_modified:
            payload["dateModified"] = date_modified.isoformat()

    script_id = "website-spec-jsonld"
    node = soup.find("script", attrs={"id": script_id})
    payload_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))

    if node is None:
        node = soup.new_tag(
            "script",
            attrs={"type": "application/ld+json", "id": script_id},
        )
        node.string = payload_json
        soup.head.append(node)
        return True

    if node.string != payload_json:
        node.string = payload_json
        return True

    return False


def _ensure_head_basics(soup, *, site_url: str, route: str) -> bool:
    changed = False
    # One scan each for the head's links and metas; every upsert below shares
    # them rather than rescanning the document per tag.
    links = _link_index(soup)
    metas = _meta_index(soup)
    canonical = _canonical_url(site_url, route)
    description = _description_for_page(soup)
    title = _title_for_page(soup)

    # Add preconnect links for performance optimization
    third_party_domains = [
        "https://scripts.simpleanalyticscdn.com",
        "https://cdnjs.cloudflare.com",
        "https://cdn.jsdelivr.net",
        "https://www.wikidata.org",
    ]
    for domain in third_party_domains:
        changed |= _upsert_link(soup, rel="preconnect", href=domain, index=links)

    # Add DNS-prefetch for CDN and external resources (fallback for browsers not supporting preconnect)
    dns_prefetch_domains = [
        "https://cdnjs.cloudflare.com",
        "https://cdn.jsdelivr.net",
        "https://www.wikidata.org",
        "https://hypothes.is",
    ]
    for domain in dns_prefetch_domains:
        changed |= _upsert_link(soup, rel="dns-prefetch", href=domain, index=links)

    changed |= _upsert_link(soup, rel="canonical", href=canonical, index=links)
    changed |= _upsert_link(
        soup,
        index=links,
        rel="alternate",
        href=f"{site_url.rstrip('/')}/rss.xml",
        type="application/rss+xml",
        title="Adriano Rutz RSS Feed",
    )
    changed |= _upsert_link(
        soup,
        index=links,
        rel="alternate",
        href=f"{site_url.rstrip('/')}/posts.json",
        type="application/feed+json",
        title="Adriano Rutz JSON Feed",
    )
    changed |= _upsert_link(
        soup,
        index=links,
        rel="sitemap",
        href=f"{site_url.rstrip('/')}/sitemap.xml",
    )
    changed |= _upsert_link(
        soup,
        index=links,
        rel="author",
        href=f"{site_url.rstrip('/')}/humans.txt",
    )
    changed |= _upsert_link(soup, rel="manifest", href="/site.webmanifest", index=links)
    changed |= _upsert_meta(
        soup,
        index=metas,
        attr_name="name",
        attr_value="description",
        content=description,
    )
    changed |= _upsert_meta(
        soup,
        index=metas,
        attr_name="name",
        attr_value="color-scheme",
        content="light dark",
    )
    changed |= _upsert_meta(
        soup,
        index=metas,
        attr_name="name",
        attr_value="theme-color",
        content="#ffffff",
        media="(prefers-color-scheme: light)",
    )

    dark_theme_meta = _meta_matching(
        metas,
        "name",
        "theme-color",
        {"media": "(prefers-color-scheme: dark)"},
    )
    if dark_theme_meta is None:
        soup.head.append(
            soup.new_tag(
                "meta",
                attrs={
                    "name": "theme-color",
                    "content": "#0f172a",
                    "media": "(prefers-color-scheme: dark)",
                },
            ),
        )
        changed = True
    elif dark_theme_meta.get("content") != "#0f172a":
        dark_theme_meta["content"] = "#0f172a"
        changed = True

    og_type = "article" if route.startswith(("/posts/", "/articles/")) else "website"
    og_image_node = _meta_matching(metas, "property", "og:image", {})
    og_image = (
        og_image_node.get("content", "").strip()
        if og_image_node
        else f"{site_url.rstrip('/')}/images/favicon/favicon.ico"
    )

    changed |= _upsert_meta(
        soup,
        index=metas,
        attr_name="property",
        attr_value="og:title",
        content=title,
    )
    changed |= _upsert_meta(
        soup,
        index=metas,
        attr_name="property",
        attr_value="og:description",
        content=description,
    )
    changed |= _upsert_meta(
        soup,
        index=metas,
        attr_name="property",
        attr_value="og:url",
        content=canonical,
    )
    changed |= _upsert_meta(
        soup,
        index=metas,
        attr_name="property",
        attr_value="og:type",
        content=og_type,
    )
    changed |= _upsert_meta(
        soup,
        index=metas,
        attr_name="property",
        attr_value="og:image",
        content=og_image,
    )

    changed |= _upsert_meta(
        soup,
        index=metas,
        attr_name="name",
        attr_value="twitter:card",
        content="summary_large_image",
    )
    changed |= _upsert_meta(
        soup,
        index=metas,
        attr_name="name",
        attr_value="twitter:title",
        content=title,
    )
    changed |= _upsert_meta(
        soup,
        index=metas,
        attr_name="name",
        attr_value="twitter:description",
        content=description,
    )
    changed |= _upsert_meta(
        soup,
        index=metas,
        attr_name="name",
        attr_value="twitter:image",
        content=og_image,
    )

    changed |= _inject_jsonld(
        soup,
        site_url=site_url,
        canonical_url=canonical,
        route=route,
        title=title,
        description=description,
    )

    return changed


def enforce_website_spec(html_files: list[Path], site_url: str) -> None:
    """Apply metadata and discovery defaults to all rendered HTML pages."""
    fixed_count = 0
    changed_count = 0

    site_dir = None
    for html_file in html_files:
        if site_dir is None:
            site_dir = html_file.parent
            while site_dir.name != "_site" and site_dir.parent != site_dir:
                site_dir = site_dir.parent

        content = html_file.read_text(encoding="utf-8")

        soup = BeautifulSoup(content, "html.parser")
        if not soup.head:
            continue

        route = _route_from_html(html_file, site_dir)
        if _ensure_head_basics(soup, site_url=site_url, route=route):
            _ = html_file.write_text(str(soup), encoding="utf-8")
            changed_count += 1

        fixed_count += 1

    logger.info(
        "Website spec hardening inspected %s HTML file(s); updated %s file(s)",
        fixed_count,
        changed_count,
    )
