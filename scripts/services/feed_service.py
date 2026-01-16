"""Feed service for RSS/JSON feed processing."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
from lxml import etree

from infrastructure.filesystem import FileSystem
from infrastructure.logger import get_logger
from infrastructure.yaml_loader import YamlLoader

logger = get_logger(__name__)


class FeedService:
    """Handles RSS and JSON feed processing."""

    DOI_URL_PREFIX = "https://doi.org/"

    def __init__(
        self,
        filesystem: FileSystem,
        yaml_loader: YamlLoader,
    ):
        """Initialize feed service.

        Args:
            filesystem: FileSystem instance
            yaml_loader: YamlLoader instance
        """
        self.fs = filesystem
        self.yaml = yaml_loader

    def inject_doi_in_rss(
        self,
        rss_path: Path,
        qmd_files: list[Path],
    ) -> bool:
        """Inject DOIs into RSS feed items.

        Args:
            rss_path: Path to RSS file
            qmd_files: List of QMD source files

        Returns:
            True if file was modified
        """
        # Build DOI mapping from QMD files
        doi_mapping = self._build_doi_mapping(qmd_files)
        if not doi_mapping:
            logger.debug("No DOIs found in QMD files")
            return False

        # Load RSS
        if not self.fs.exists(rss_path):
            logger.warning(f"RSS file not found: {rss_path}")
            return False

        try:
            content = self.fs.read_text(rss_path)
            soup = BeautifulSoup(content, "xml")
        except Exception as e:
            logger.error(f"Failed to parse RSS: {e}")
            return False

        # Inject DOIs into items
        changed = False
        items = soup.find_all("item")

        for item in items:
            title_elem = item.find("title")
            if not title_elem:
                continue

            title = title_elem.get_text().strip()
            doi = doi_mapping.get(title)

            if doi:
                # Check if already has DOI
                existing_doi = item.find("guid")
                if existing_doi and existing_doi.get_text().strip() == doi:
                    continue

                # Add or update guid element with DOI
                if existing_doi:
                    existing_doi.string = doi
                else:
                    guid_tag = soup.new_tag("guid")
                    guid_tag.string = doi
                    item.append(guid_tag)

                changed = True
                logger.debug(f"Injected DOI for: {title}")

        # Save if changed
        if changed:
            self.fs.write_text(rss_path, str(soup))
            logger.info(f"✓ Injected DOIs into {rss_path.name}")

        return changed

    def _build_doi_mapping(self, qmd_files: list[Path]) -> dict[str, str]:
        """Build mapping from titles to DOIs.

        Args:
            qmd_files: List of QMD files

        Returns:
            Dictionary mapping titles to DOI URLs
        """
        doi_mapping = {}

        for qmd_path in qmd_files:
            metadata = self.yaml.load_from_path(qmd_path)
            if not metadata:
                continue

            title = metadata.get("title")
            doi = metadata.get("doi")

            if title and doi:
                # Normalize DOI to full URL
                doi = doi.strip()
                if not doi.startswith("http"):
                    doi = self.DOI_URL_PREFIX + doi

                doi_mapping[title.strip()] = doi

        logger.debug(f"Built DOI mapping for {len(doi_mapping)} items")
        return doi_mapping

    def inject_cito_in_rss(
        self,
        rss_path: Path,
        citation_properties: dict[str, list[str]],
    ) -> bool:
        """Inject CiTO annotations into RSS feed items.

        Args:
            rss_path: Path to RSS file
            citation_properties: Dictionary of citation properties

        Returns:
            True if file was modified
        """
        if not self.fs.exists(rss_path):
            logger.warning(f"RSS file not found: {rss_path}")
            return False

        try:
            content = self.fs.read_text(rss_path)
            soup = BeautifulSoup(content, "xml")
        except Exception as e:
            logger.error(f"Failed to parse RSS: {e}")
            return False

        # Inject CiTO annotations into description fields
        changed = False
        items = soup.find_all("item")

        for item in items:
            description_elem = item.find("description")
            if not description_elem:
                continue

            description_html = description_elem.get_text()

            # Parse description HTML
            desc_soup = BeautifulSoup(description_html, "html.parser")

            # Find bibliography entries
            refs = desc_soup.find("div", id="refs")
            if refs:
                entries = refs.find_all("div", class_="csl-entry")

                for entry in entries:
                    entry_id = entry.get("id", "")
                    if entry_id.startswith("ref-"):
                        cite_id = entry_id[4:]
                        props = citation_properties.get(cite_id, [])

                        if props and not entry.find("span", class_="cito"):
                            # Add CiTO annotation
                            cito_span = desc_soup.new_tag("span", **{"class": "cito"})
                            camel_props = [self._snake_to_camel(p) for p in props]
                            annotation = " ".join(f"[cito:{p}]" for p in camel_props)
                            cito_span.string = " " + annotation
                            entry.append(cito_span)
                            changed = True

                # Update description if changed
                if changed:
                    description_elem.string = str(desc_soup)

        # Save if changed
        if changed:
            self.fs.write_text(rss_path, str(soup))
            logger.info(f"✓ Injected CiTO annotations into {rss_path.name}")

        return changed

    def convert_rss_to_json_feed(
        self,
        rss_path: Path,
        json_feed_path: Path,
    ) -> bool:
        """Convert RSS feed to JSON Feed format.

        Args:
            rss_path: Path to RSS file
            json_feed_path: Path to output JSON Feed file

        Returns:
            True if successful
        """
        if not self.fs.exists(rss_path):
            logger.warning(f"RSS file not found: {rss_path}")
            return False

        try:
            content = self.fs.read_text(rss_path)
            tree = etree.fromstring(content.encode("utf-8"))
        except Exception as e:
            logger.error(f"Failed to parse RSS with lxml: {e}")
            return False

        # Extract channel metadata
        channel = tree.find("channel")
        if channel is None:
            logger.error("No channel found in RSS")
            return False

        # Build JSON Feed
        json_feed = {
            "version": "https://jsonfeed.org/version/1.1",
            "title": self._get_element_text(channel, "title", ""),
            "home_page_url": self._get_element_text(channel, "link", ""),
            "feed_url": str(json_feed_path),
        }

        # Add description if present
        description = self._get_element_text(channel, "description")
        if description:
            json_feed["description"] = description

        # Convert items
        items = []
        for item_elem in channel.findall("item"):
            item = self._convert_rss_item_to_json(item_elem)
            if item:
                items.append(item)

        json_feed["items"] = items

        # Write JSON Feed
        try:
            json_str = json.dumps(json_feed, indent=2, ensure_ascii=False)
            self.fs.write_text(json_feed_path, json_str)
            logger.info(f"✓ Converted RSS to JSON Feed: {json_feed_path.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to write JSON Feed: {e}")
            return False

    def _convert_rss_item_to_json(self, item_elem) -> Optional[dict]:
        """Convert RSS item to JSON Feed item.

        Args:
            item_elem: lxml element for RSS item

        Returns:
            JSON Feed item dictionary or None
        """
        title = self._get_element_text(item_elem, "title")
        if not title:
            return None

        item = {"title": title}

        # Add link
        link = self._get_element_text(item_elem, "link")
        if link:
            item["url"] = link

        # Add ID (prefer GUID/DOI)
        guid = self._get_element_text(item_elem, "guid")
        if guid:
            item["id"] = guid
        elif link:
            item["id"] = link

        # Add content
        description = self._get_element_text(item_elem, "description")
        if description:
            item["content_html"] = description

        # Add date
        pub_date = self._get_element_text(item_elem, "pubDate")
        if pub_date:
            try:
                # Parse RSS date format
                dt = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %z")
                item["date_published"] = dt.isoformat()
            except Exception:
                pass

        return item

    def _get_element_text(
        self,
        parent,
        tag_name: str,
        default: str = "",
    ) -> str:
        """Get text from XML element.

        Args:
            parent: Parent element
            tag_name: Tag name to find
            default: Default value if not found

        Returns:
            Element text or default
        """
        elem = parent.find(tag_name)
        if elem is not None and elem.text:
            return elem.text.strip()
        return default

    @staticmethod
    def _snake_to_camel(snake_str: str) -> str:
        """Convert snake_case to camelCase.

        Args:
            snake_str: Snake case string

        Returns:
            Camel case string
        """
        parts = snake_str.split("_")
        return parts[0] + "".join(word.capitalize() for word in parts[1:])

    def process_feeds(
        self,
        rss_path: Path,
        json_feed_path: Path,
        qmd_files: list[Path],
        citation_properties: dict[str, list[str]],
    ) -> bool:
        """Complete feed processing pipeline.

        Args:
            rss_path: Path to RSS file
            json_feed_path: Path to JSON Feed output
            qmd_files: List of QMD source files
            citation_properties: Citation properties dictionary

        Returns:
            True if successful
        """
        logger.info("Processing feeds...")

        # Inject DOIs
        self.inject_doi_in_rss(rss_path, qmd_files)

        # Inject CiTO annotations
        self.inject_cito_in_rss(rss_path, citation_properties)

        # Convert to JSON Feed
        success = self.convert_rss_to_json_feed(rss_path, json_feed_path)

        if success:
            logger.info("✓ Feed processing complete")

        return success
