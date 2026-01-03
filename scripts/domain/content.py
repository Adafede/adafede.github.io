"""Content metadata and feed models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ContentMetadata:
    """Metadata for content items (posts, articles, etc.)."""

    title: str
    url: str
    date_published: Optional[datetime] = None
    date_modified: Optional[datetime] = None
    summary: Optional[str] = None
    content_html: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    authors: list[dict] = field(default_factory=list)

    def to_json_feed_item(self) -> dict:
        """Convert to JSON Feed item format.

        Returns:
            Dictionary in JSON Feed format
        """
        item = {
            "title": self.title,
            "url": self.url,
        }

        if self.date_published:
            item["date_published"] = self.date_published.isoformat()

        if self.date_modified:
            item["date_modified"] = self.date_modified.isoformat()

        if self.summary:
            item["summary"] = self.summary

        if self.content_html:
            item["content_html"] = self.content_html

        if self.tags:
            item["tags"] = self.tags

        if self.authors:
            item["authors"] = self.authors

        return item


@dataclass
class FeedItem:
    """RSS/Atom feed item."""

    title: str
    link: str
    description: Optional[str] = None
    pub_date: Optional[datetime] = None
    guid: Optional[str] = None

    def to_rss_item(self) -> str:
        """Convert to RSS XML item element.

        Returns:
            RSS item XML string
        """
        parts = ["<item>"]
        parts.append(f"  <title>{self._escape_xml(self.title)}</title>")
        parts.append(f"  <link>{self._escape_xml(self.link)}</link>")

        if self.description:
            parts.append(
                f"  <description>{self._escape_xml(self.description)}</description>"
            )

        if self.pub_date:
            # RFC 822 format for RSS
            date_str = self.pub_date.strftime("%a, %d %b %Y %H:%M:%S +0000")
            parts.append(f"  <pubDate>{date_str}</pubDate>")

        if self.guid:
            parts.append(f"  <guid>{self._escape_xml(self.guid)}</guid>")

        parts.append("</item>")
        return "\n".join(parts)

    @staticmethod
    def _escape_xml(text: str) -> str:
        """Escape XML special characters.

        Args:
            text: Text to escape

        Returns:
            Escaped text
        """
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )
