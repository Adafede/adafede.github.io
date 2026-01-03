"""Convert RSS feed to JSON Feed format.

Converts an RSS XML feed to JSON Feed format with additional metadata
and modification tracking. Uses infrastructure layer for logging.
"""

import json
import os
import subprocess
from datetime import datetime
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from lxml import etree

import sys
from pathlib import Path

# Add parent directory to path for infrastructure imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure import get_logger

logger = get_logger(__name__)

# Centralized author mapping
AUTHOR_MAPPINGS = {
    "Adriano Rutz": {
        "url": "https://orcid.org/0000-0003-0443-9902",
        "_orcid": "0000-0003-0443-9902",
    },
    # Add more authors as needed
}


def get_element_text(parent, tag_name, namespace=None):
    if namespace:
        element = parent.find(f"{{{namespace}}}{tag_name}")
    else:
        element = parent.find(tag_name)

    if element is not None and element.text:
        return element.text.strip()
    return None


def create_author_info(author_name, include_orcid=True):
    if not author_name or author_name not in AUTHOR_MAPPINGS:
        return {"name": author_name} if author_name else None

    author_info = {"name": author_name}
    mapping = AUTHOR_MAPPINGS[author_name]

    if mapping.get("url"):
        author_info["url"] = mapping["url"]

    if include_orcid and mapping.get("_orcid"):
        author_info["_orcid"] = mapping["_orcid"]

    return author_info


def extract_author_info(channel):
    # Try channel first, then first item
    author_name = (
        get_element_text(channel, "creator", "http://purl.org/dc/elements/1.1/") or None
    )

    if not author_name:
        items = channel.findall("item")
        if items:
            author_name = get_element_text(
                items[0],
                "creator",
                "http://purl.org/dc/elements/1.1/",
            )

    return create_author_info(author_name, include_orcid=True) if author_name else {}


def extract_feed_metadata(channel):
    metadata = {}

    # Basic metadata extraction
    fields = {
        "title": "title",
        "home_page_url": "link",
        "description": "description",
        "language": "language",
    }

    for json_field, xml_field in fields.items():
        value = get_element_text(channel, xml_field)
        if value:
            metadata[json_field] = value

    atom_link = channel.find("{http://www.w3.org/2005/Atom}link")
    if atom_link is not None and atom_link.get("rel") == "self":
        href = atom_link.get("href")
        if href:
            metadata["feed_url"] = href.replace(".xml", ".json")

    return metadata


def get_qmd_modification_time(item_url, base_url=None):
    if not item_url:
        return None

    try:
        if base_url and item_url.startswith(base_url):
            relative_path = item_url[len(base_url) :].strip("/")
        else:
            parsed = urlparse(item_url)
            relative_path = parsed.path.strip("/")

        if relative_path.endswith(".html"):
            relative_path = relative_path[:-5]

        qmd_candidates = [
            f"{relative_path}/index.qmd",
            f"{relative_path}.qmd",
            f"posts/{relative_path}/index.qmd",
            f"posts/{relative_path}.qmd",
        ]

        for candidate in qmd_candidates:
            if os.path.isfile(candidate):
                git_date = get_git_commit_date(candidate)
                if git_date:
                    return git_date
                else:
                    mod_timestamp = os.path.getmtime(candidate)
                    return datetime.fromtimestamp(mod_timestamp).isoformat()

        return None

    except Exception as e:
        print(f"Warning: Could not get .qmd modification time for {item_url}: {e}")
        return None


def is_file_modified(file_path):
    """Check if a file has uncommitted changes."""
    try:
        import subprocess

        result = subprocess.run(
            [
                "git",
                "diff",
                "--quiet",
                "HEAD",
                "--",
                file_path,
            ],
            cwd=os.path.dirname(file_path) or ".",
            capture_output=True,
        )
        # git diff --quiet returns 0 if no differences, 1 if differences exist
        return result.returncode != 0
    except Exception:
        # If git command fails, assume file is modified to be safe
        return True


def get_git_commit_date(file_path):
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        return result.stdout.strip() or None
    except subprocess.CalledProcessError:
        return None


def extract_item_data(item, base_url=None):
    item_data = {}

    # Basic item fields
    fields = {
        "title": "title",
        "url": "link",
        "id": "guid",
    }

    for json_field, xml_field in fields.items():
        value = get_element_text(item, xml_field)
        if value:
            item_data[json_field] = value

    # Handle description and extract summary
    description = get_element_text(item, "description")
    if description:
        item_data["content_html"] = description
        soup = BeautifulSoup(description, "html.parser")
        first_paragraph = soup.find("p")
        if first_paragraph:
            item_data["summary"] = first_paragraph.get_text().strip()

        # Extract image from content
        first_img = soup.find("img")
        if first_img and first_img.get("src"):
            src = first_img.get("src")
            if src.startswith("/") and base_url:
                item_data["image"] = base_url.rstrip("/") + src
            elif src.startswith("http"):
                item_data["image"] = src

    # Handle publication date
    pubdate = get_element_text(item, "pubDate")
    if pubdate:
        try:
            from email.utils import parsedate_to_datetime

            dt = parsedate_to_datetime(pubdate)
            iso_date = dt.isoformat()
            item_data["date_published"] = iso_date
        except Exception:
            item_data["date_published"] = pubdate

    # Get .qmd file modification time for this item
    item_url = item_data.get("url")
    qmd_mod_time = get_qmd_modification_time(item_url, base_url)

    if qmd_mod_time:
        item_data["date_modified"] = qmd_mod_time
    else:
        try:
            from email.utils import parsedate_to_datetime

            dt = parsedate_to_datetime(pubdate)
            iso_date = dt.isoformat()
            item_data["date_modified"] = iso_date
        except Exception:
            item_data["date_modified"] = pubdate

    # Handle categories/tags
    categories = item.findall("category")
    if categories:
        item_data["tags"] = [
            cat.text.strip() for cat in categories if cat.text and cat.text.strip()
        ]

    # Handle item author
    author_name = get_element_text(item, "creator", "http://purl.org/dc/elements/1.1/")
    if author_name:
        author_info = create_author_info(author_name, include_orcid=False)
        if author_info:
            item_data["authors"] = [author_info]

    # Handle item references (need to parse description again for this)
    if description:
        soup = BeautifulSoup(description, "html.parser")
        refs_div = soup.find("div", class_="references")
        references = []
        if refs_div:
            entries = refs_div.find_all("div", class_="csl-entry")
            for entry in entries:
                ref = {}
                link = entry.find("a", href=True)
                if link:
                    url = link["href"]
                    if url.startswith("http://dx.doi.org/") or url.startswith(
                        "https://doi.org/",
                    ):
                        doi = url.split("doi.org/")[-1]
                        ref["url"] = url.replace(
                            "http://dx.doi.org/",
                            "https://doi.org/",
                        )
                        ref["doi"] = doi
                # Find all cito annotations
                cito_spans = entry.find_all("span", class_="cito")
                cito_relations = []
                for span in cito_spans:
                    text = span.get_text(strip=True)
                    if text.startswith("[cito:") and text.endswith("]"):
                        cito_relations.append(
                            text[6:-1],
                        )  # remove [cito:] and trailing ]
                if ref.get("doi") and cito_relations:
                    ref["cito"] = cito_relations
                    references.append(ref)
        if references:
            item_data["_references"] = references

    # Handle DOI
    ## After discussion with Martin Fenner about where the DOI should be in comparison to Atom/RSS
    doi = get_element_text(item, "doi")
    if doi:
        item_data["id"] = doi

    # Placeholder for funding info (TODO not there yet, return an empty one)
    # item_data["_funding"] = []
    # TODO TO GET SOMETHING LIKE
    # "_funding": [{"award": { "title" : "The Virtual Human Platform for Safety Assessment", "acronym" : "VHP4Safety", "uri" : "drc.filenumber:nwa129219272" }, "funder": { "name": "Dutch Research Council", "ror": "04jsz6e67" } }],

    return item_data


def convert_rss_to_json_feed(rss_path, json_feed_path):
    """Convert RSS XML to JSON Feed format."""
    if not os.path.isfile(rss_path):
        print(f"RSS file not found at {rss_path}")
        return

    try:
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.parse(rss_path, parser)
        root = tree.getroot()

        channel = root.find("channel")
        if channel is None:
            print(f"No channel found in RSS file {rss_path}")
            return

        # Build JSON Feed structure
        json_feed = {
            "version": "https://jsonfeed.org/version/1.1",
            "title": "",
            "description": "",
            "home_page_url": "",
            "feed_url": "",
            "language": "en",
            "items": [],
        }

        # Extract and apply feed metadata
        metadata = extract_feed_metadata(channel)
        json_feed.update(metadata)

        # Extract and add author information
        author_info = extract_author_info(channel)
        if author_info:
            json_feed["authors"] = [author_info]

        # Extract items
        items = channel.findall("item")
        base_url = json_feed.get("home_page_url")

        for item in items:
            item_data = extract_item_data(item, base_url)
            if item_data:
                json_feed["items"].append(item_data)

        # Write JSON Feed file
        with open(json_feed_path, "w", encoding="utf-8") as f:
            json.dump(json_feed, f, indent=2, ensure_ascii=False)

        print(f"Generated JSON Feed: {json_feed_path}")

    except Exception as e:
        print(f"Error converting RSS to JSON: {e}")


if __name__ == "__main__":
    convert_rss_to_json_feed("_site/posts.xml", "_site/posts.json")
