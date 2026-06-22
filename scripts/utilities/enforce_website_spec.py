"""Website-spec metadata hardening for rendered HTML pages.

Adds missing head tags so generated pages meet modern baseline expectations.
"""

import json
from datetime import date
from pathlib import Path
from typing import List

from infrastructure import get_logger

logger = get_logger(__name__)

DEFAULT_DESCRIPTION = (
    "Personal website of Adriano Rutz - Swiss Pharmaceutical Scientist "
    "specializing in metabolomics, mass spectrometry, and natural products research."
)


def _upsert_meta(
    soup,
    *,
    attr_name: str,
    attr_value: str,
    content: str,
    **extra_attrs,
) -> bool:
    """Create or update a meta tag and return whether it changed."""
    selector = {attr_name: attr_value, **extra_attrs}
    node = soup.find("meta", attrs=selector)
    if node is None:
        attrs = {"content": content, attr_name: attr_value, **extra_attrs}
        soup.head.append(soup.new_tag("meta", attrs=attrs))
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


def _upsert_link(soup, *, rel: str, href: str, **attrs) -> bool:
    """Create or update a link tag and return whether it changed."""
    node = None
    for candidate in soup.find_all("link"):
        rel_values = candidate.get("rel", [])
        rel_tokens = (
            rel_values if isinstance(rel_values, list) else str(rel_values).split()
        )
        if rel not in rel_tokens:
            continue

        if all(candidate.get(key) == value for key, value in attrs.items()):
            node = candidate
            break

    if node is None:
        link_attrs = {"rel": rel, "href": href, **attrs}
        soup.head.append(soup.new_tag("link", attrs=link_attrs))
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
    if route.startswith("/posts/") or route.startswith("/articles/"):
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
        changed |= _upsert_link(soup, rel="preconnect", href=domain)

    # Add DNS-prefetch for CDN and external resources (fallback for browsers not supporting preconnect)
    dns_prefetch_domains = [
        "https://cdnjs.cloudflare.com",
        "https://cdn.jsdelivr.net",
        "https://www.wikidata.org",
        "https://hypothes.is",
    ]
    for domain in dns_prefetch_domains:
        changed |= _upsert_link(soup, rel="dns-prefetch", href=domain)

    changed |= _upsert_link(soup, rel="canonical", href=canonical)
    changed |= _upsert_link(
        soup,
        rel="alternate",
        href=f"{site_url.rstrip('/')}/rss.xml",
        type="application/rss+xml",
        title="Adriano Rutz RSS Feed",
    )
    changed |= _upsert_link(
        soup,
        rel="alternate",
        href=f"{site_url.rstrip('/')}/posts.json",
        type="application/feed+json",
        title="Adriano Rutz JSON Feed",
    )
    changed |= _upsert_link(
        soup,
        rel="sitemap",
        href=f"{site_url.rstrip('/')}/sitemap.xml",
    )
    changed |= _upsert_link(
        soup,
        rel="author",
        href=f"{site_url.rstrip('/')}/humans.txt",
    )
    changed |= _upsert_link(soup, rel="manifest", href="/site.webmanifest")
    changed |= _upsert_link(
        soup,
        rel="apple-touch-icon",
        href="/images/favicon/apple-touch-icon.png",
    )

    changed |= _upsert_meta(
        soup,
        attr_name="name",
        attr_value="description",
        content=description,
    )
    changed |= _upsert_meta(
        soup,
        attr_name="name",
        attr_value="color-scheme",
        content="light dark",
    )
    changed |= _upsert_meta(
        soup,
        attr_name="name",
        attr_value="theme-color",
        content="#ffffff",
        media="(prefers-color-scheme: light)",
    )

    dark_theme_meta = soup.find(
        "meta",
        attrs={"name": "theme-color", "media": "(prefers-color-scheme: dark)"},
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

    og_type = (
        "article"
        if route.startswith("/posts/") or route.startswith("/articles/")
        else "website"
    )
    og_image = (
        soup.find("meta", attrs={"property": "og:image"}).get("content", "").strip()
        if soup.find("meta", attrs={"property": "og:image"})
        else f"{site_url.rstrip('/')}/images/favicon/favicon.ico"
    )

    changed |= _upsert_meta(
        soup,
        attr_name="property",
        attr_value="og:title",
        content=title,
    )
    changed |= _upsert_meta(
        soup,
        attr_name="property",
        attr_value="og:description",
        content=description,
    )
    changed |= _upsert_meta(
        soup,
        attr_name="property",
        attr_value="og:url",
        content=canonical,
    )
    changed |= _upsert_meta(
        soup,
        attr_name="property",
        attr_value="og:type",
        content=og_type,
    )
    changed |= _upsert_meta(
        soup,
        attr_name="property",
        attr_value="og:image",
        content=og_image,
    )

    changed |= _upsert_meta(
        soup,
        attr_name="name",
        attr_value="twitter:card",
        content="summary_large_image",
    )
    changed |= _upsert_meta(
        soup,
        attr_name="name",
        attr_value="twitter:title",
        content=title,
    )
    changed |= _upsert_meta(
        soup,
        attr_name="name",
        attr_value="twitter:description",
        content=description,
    )
    changed |= _upsert_meta(
        soup,
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


def enforce_website_spec(html_files: List[Path], site_url: str) -> None:
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
        from bs4 import BeautifulSoup  # local import to keep import surface minimal

        soup = BeautifulSoup(content, "html.parser")
        if not soup.head:
            continue

        route = _route_from_html(html_file, site_dir)
        if _ensure_head_basics(soup, site_url=site_url, route=route):
            html_file.write_text(str(soup), encoding="utf-8")
            changed_count += 1

        fixed_count += 1

    logger.info(
        "Website spec hardening inspected %s HTML file(s); updated %s file(s)",
        fixed_count,
        changed_count,
    )
