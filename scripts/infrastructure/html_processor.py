"""HTML parsing and manipulation utilities using BeautifulSoup."""

from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup, Tag

from .logger import get_logger

logger = get_logger(__name__)


class HtmlProcessor:
    """Provides high-level operations for HTML manipulation."""

    def __init__(self, parser: str = "html.parser"):
        """Initialize HTML processor.

        Args:
            parser: BeautifulSoup parser to use
        """
        self.parser = parser

    def load_from_path(self, path: Path) -> Optional[BeautifulSoup]:
        """Load and parse HTML file.

        Args:
            path: Path to HTML file

        Returns:
            BeautifulSoup object or None if file doesn't exist
        """
        path = Path(path)

        if not path.exists():
            logger.debug(f"HTML file not found: {path}")
            return None

        try:
            content = path.read_text(encoding="utf-8")
            return BeautifulSoup(content, self.parser)
        except Exception as e:
            logger.error(f"Failed to parse HTML from {path}: {e}")
            return None

    def load_from_string(self, html_str: str) -> BeautifulSoup:
        """Parse HTML from string.

        Args:
            html_str: HTML content as string

        Returns:
            BeautifulSoup object
        """
        return BeautifulSoup(html_str, self.parser)

    def save_to_path(self, soup: BeautifulSoup, path: Path) -> None:
        """Save BeautifulSoup object to file.

        Args:
            soup: BeautifulSoup object to save
            path: Output file path
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        html_str = str(soup)
        path.write_text(html_str, encoding="utf-8")
        logger.debug(f"Saved HTML to {path}")

    def find_element_by_id(
        self,
        soup: BeautifulSoup,
        element_id: str,
    ) -> Optional[Tag]:
        """Find element by ID.

        Args:
            soup: BeautifulSoup object
            element_id: Element ID to search for

        Returns:
            Found element or None
        """
        return soup.find(id=element_id)

    def find_elements_by_class(
        self,
        soup: BeautifulSoup,
        class_name: str,
        tag: Optional[str] = None,
    ) -> list[Tag]:
        """Find elements by class name.

        Args:
            soup: BeautifulSoup object
            class_name: CSS class name
            tag: Optional tag name to filter by

        Returns:
            List of matching elements
        """
        if tag:
            return soup.find_all(tag, class_=class_name)
        return soup.find_all(class_=class_name)

    def create_element(
        self,
        soup: BeautifulSoup,
        tag: str,
        text: Optional[str] = None,
        **attrs,
    ) -> Tag:
        """Create a new HTML element.

        Args:
            soup: BeautifulSoup object (for element creation)
            tag: Tag name
            text: Optional text content
            **attrs: HTML attributes as keyword arguments

        Returns:
            New Tag object
        """
        element = soup.new_tag(tag, **attrs)
        if text:
            element.string = text
        return element

    def append_element(
        self,
        parent: Tag,
        child: Tag,
    ) -> None:
        """Append child element to parent.

        Args:
            parent: Parent element
            child: Child element to append
        """
        parent.append(child)

    def has_class(self, element: Tag, class_name: str) -> bool:
        """Check if element has a specific class.

        Args:
            element: Tag to check
            class_name: Class name to look for

        Returns:
            True if element has the class
        """
        classes = element.get("class", [])
        return class_name in classes

    def get_attribute(
        self,
        element: Tag,
        attr_name: str,
        default: Optional[str] = None,
    ) -> Optional[str]:
        """Get element attribute value.

        Args:
            element: Tag to get attribute from
            attr_name: Attribute name
            default: Default value if attribute doesn't exist

        Returns:
            Attribute value or default
        """
        return element.get(attr_name, default)

    def set_attribute(
        self,
        element: Tag,
        attr_name: str,
        value: str,
    ) -> None:
        """Set element attribute.

        Args:
            element: Tag to modify
            attr_name: Attribute name
            value: Attribute value
        """
        element[attr_name] = value
