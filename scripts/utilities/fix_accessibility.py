"""
Accessibility fixer for HTML files.

Fixes common WAVE accessibility issues in generated HTML files.
"""

import sys
from pathlib import Path
from typing import List

# Add parent directory to path for infrastructure imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure import FileSystem, HtmlProcessor, get_logger

logger = get_logger(__name__)


class AccessibilityFixer:
    """Fixes accessibility issues in HTML files."""

    def __init__(self, fs: FileSystem, html_processor: HtmlProcessor):
        """Initialize the accessibility fixer.

        Args:
            fs: FileSystem instance
            html_processor: HtmlProcessor instance
        """
        self.fs = fs
        self.html_processor = html_processor

    def fix_html_file(self, html_path: Path) -> bool:
        """Fix accessibility issues in an HTML file.

        Args:
            html_path: Path to HTML file

        Returns:
            True if changes were made, False otherwise
        """
        if not self.fs.exists(html_path):
            logger.warning(f"HTML file not found: {html_path}")
            return False

        soup = self.html_processor.load_from_path(html_path)
        if not soup:
            return False

        modified = False

        # Fix 1: Add lang attribute to links with non-English text
        modified |= self._fix_link_language(soup)

        # Fix 2: Ensure all images have alt text
        modified |= self._fix_image_alt_text(soup)

        # Fix 3: Fix empty links
        modified |= self._fix_empty_links(soup)

        # Fix 4: Add ARIA labels where needed
        modified |= self._fix_aria_labels(soup)

        # Fix 5: Ensure heading hierarchy
        modified |= self._fix_heading_hierarchy(soup)

        # Fix 6: Add titles to iframes
        modified |= self._fix_iframe_titles(soup)

        # Fix 7: Fix incorrect ARIA roles
        modified |= self._fix_aria_roles(soup)

        # Fix 8: Fix icon-only links in navigation
        modified |= self._fix_nav_icon_links(soup)

        # Fix 9: Fix search inputs without labels
        modified |= self._fix_search_inputs(soup)

        # Fix 10: Fix table accessibility
        modified |= self._fix_table_accessibility(soup)

        # Fix 11: Fix redundant links
        modified |= self._fix_redundant_links(soup)

        # Fix 12: Fix listing grid accessibility
        modified |= self._fix_listing_grids(soup)

        # Fix 13: Fix listing item links
        modified |= self._fix_listing_item_links(soup)

        # Fix 14: Fix skip links
        modified |= self._fix_skip_links(soup)

        # Fix 15: Fix missing main landmark
        modified |= self._fix_main_landmark(soup)

        # Save if modified
        if modified:
            self.fs.write_text(html_path, str(soup))
            logger.info(f"✓ Fixed accessibility issues in {html_path.name}")
            return True

        return False

    def _fix_link_language(self, soup) -> bool:
        """Add hreflang attributes to external links."""
        modified = False
        # Implementation would check for external links and add appropriate lang attributes
        return modified

    def _fix_image_alt_text(self, soup) -> bool:
        """Ensure all images have alt text."""
        modified = False
        images = soup.find_all("img")

        for img in images:
            if not img.get("alt"):
                # Try to get meaningful alt text from context
                alt_text = self._generate_alt_text(img)
                img["alt"] = alt_text
                modified = True
                logger.debug(f"Added alt text to image: {img.get('src', 'unknown')}")

        return modified

    def _generate_alt_text(self, img) -> str:
        """Generate meaningful alt text for an image.

        Args:
            img: BeautifulSoup img element

        Returns:
            Generated alt text
        """
        # Try to get from title
        if img.get("title"):
            return img["title"]

        # Try to get from surrounding context
        parent = img.parent
        if parent and parent.name == "a":
            # If image is in a link, use link text or href
            if parent.get_text(strip=True):
                return f"Link to {parent.get_text(strip=True)}"
            elif parent.get("href"):
                return f"Link to {parent['href']}"

        # Try to extract from filename
        src = img.get("src", "")
        if src:
            filename = Path(src).stem
            # Convert underscore/hyphen to spaces and capitalize
            return filename.replace("_", " ").replace("-", " ").title()

        return "Image"

    def _fix_empty_links(self, soup) -> bool:
        """Fix links with no text content."""
        modified = False
        links = soup.find_all("a")

        for link in links:
            text = link.get_text(strip=True)
            if not text and not link.get("aria-label"):
                # Add aria-label based on context
                aria_label = self._generate_link_label(link)
                if aria_label:
                    link["aria-label"] = aria_label
                    modified = True
                    logger.debug(
                        f"Added aria-label to empty link: {link.get('href', 'unknown')}"
                    )

        return modified

    def _generate_link_label(self, link) -> str:
        """Generate aria-label for a link.

        Args:
            link: BeautifulSoup link element

        Returns:
            Generated label
        """
        # Check for icon children
        icon = link.find("i") or link.find(class_="icon")
        if icon:
            classes = icon.get("class", [])
            # Extract icon name from classes
            for cls in classes:
                if "envelope" in cls:
                    return "Email"
                elif "linkedin" in cls:
                    return "LinkedIn profile"
                elif "github" in cls:
                    return "GitHub profile"
                elif "orcid" in cls:
                    return "ORCID profile"
                elif "twitter" in cls or "x-twitter" in cls:
                    return "Twitter/X profile"
                elif "mastodon" in cls:
                    return "Mastodon profile"

        # Try to get from href
        href = link.get("href", "")
        if "mailto:" in href:
            return "Email"
        elif "linkedin.com" in href:
            return "LinkedIn profile"
        elif "github.com" in href:
            return "GitHub profile"
        elif "orcid.org" in href:
            return "ORCID profile"
        elif "twitter.com" in href or "x.com" in href:
            return "Twitter/X profile"

        return ""

    def _fix_aria_labels(self, soup) -> bool:
        """Add missing ARIA labels to interactive elements."""
        modified = False

        # Fix buttons without labels
        buttons = soup.find_all("button")
        for button in buttons:
            if not button.get_text(strip=True) and not button.get("aria-label"):
                # Try to infer from context or class
                classes = " ".join(button.get("class", []))
                if "search" in classes:
                    button["aria-label"] = "Search"
                    modified = True
                elif (
                    "menu" in classes
                    or "toggle" in classes
                    or "navbar-toggler" in classes
                ):
                    button["aria-label"] = "Toggle navigation menu"
                    modified = True

        return modified

    def _fix_heading_hierarchy(self, soup) -> bool:
        """Check and fix heading hierarchy issues."""
        modified = False

        # Fix specific issue: quarto-listing-category-title should not be h5
        category_titles = soup.find_all(class_="quarto-listing-category-title")
        for title in category_titles:
            if title.name in ["h5", "h4", "h3", "h2"]:
                # Convert to a strong element with aria-label for screen readers
                new_tag = soup.new_tag("div")
                new_tag["class"] = title.get("class", [])
                new_tag["role"] = "heading"
                new_tag["aria-level"] = "2"
                new_tag.string = title.get_text()
                title.replace_with(new_tag)
                modified = True
                logger.debug(
                    f"Converted {title.name} category title to div with role='heading'"
                )

        # Check and log remaining heading hierarchy issues
        headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])

        if not headings:
            return modified

        prev_level = 0
        for heading in headings:
            level = int(heading.name[1])
            if prev_level > 0 and level > prev_level + 1:
                logger.warning(
                    f"Heading hierarchy skip detected: {heading.name} after h{prev_level}"
                )
            prev_level = level

        return modified

    def _fix_iframe_titles(self, soup) -> bool:
        """Add title attributes to iframes for screen readers."""
        modified = False
        iframes = soup.find_all("iframe")

        for iframe in iframes:
            if not iframe.get("title"):
                # Generate title from src or context
                title = self._generate_iframe_title(iframe)
                if title:
                    iframe["title"] = title
                    modified = True
                    logger.debug(f"Added title to iframe: {title}")

        return modified

    def _generate_iframe_title(self, iframe) -> str:
        """Generate a descriptive title for an iframe.

        Args:
            iframe: BeautifulSoup iframe element

        Returns:
            Generated title
        """
        src = iframe.get("src", "")

        # Check for common embed patterns
        if "wikidata-query" in src or "scholia" in src:
            return "Interactive data visualization from Wikidata"
        elif "youtube.com" in src or "youtu.be" in src:
            return "Embedded YouTube video"
        elif "vimeo.com" in src:
            return "Embedded Vimeo video"
        elif "twitter.com" in src or "x.com" in src:
            return "Embedded Twitter/X content"
        elif "maps.google" in src or "openstreetmap" in src:
            return "Embedded map"

        # Try to infer from parent headings
        parent = iframe.parent
        while parent:
            heading = parent.find(["h1", "h2", "h3", "h4", "h5", "h6"])
            if heading:
                return f"Embedded content for {heading.get_text(strip=True)}"
            parent = parent.parent

        return "Embedded content"

    def _fix_aria_roles(self, soup) -> bool:
        """Fix incorrect ARIA role attributes."""
        modified = False

        # Fix buttons with role="menu" (should be "button")
        buttons = soup.find_all("button", role="menu")
        for button in buttons:
            button["role"] = "button"
            modified = True
            logger.debug("Fixed button role from 'menu' to 'button'")

        return modified

    def _fix_nav_icon_links(self, soup) -> bool:
        """Fix icon-only links in navigation (like RSS feeds)."""
        modified = False

        # Find nav links with icons but no text
        nav_links = soup.find_all("a", class_="nav-link")
        for link in nav_links:
            # Check if link has icon but no meaningful text
            text = link.get_text(strip=True)
            icon = link.find("i")

            if icon and not text and not link.get("aria-label"):
                # Generate label from icon class or href
                label = self._generate_icon_link_label(icon, link)
                if label:
                    link["aria-label"] = label
                    modified = True
                    logger.debug(f"Added aria-label to nav icon link: {label}")

        return modified

    def _generate_icon_link_label(self, icon, link) -> str:
        """Generate label for icon-only link.

        Args:
            icon: BeautifulSoup icon element
            link: BeautifulSoup link element

        Returns:
            Generated label
        """
        # Check icon classes
        classes = " ".join(icon.get("class", []))

        if "rss" in classes.lower():
            return "RSS Feed"
        elif "atom" in classes.lower():
            return "Atom Feed"

        # Check link href
        href = link.get("href", "").lower()
        if "rss.xml" in href or "/rss" in href:
            return "RSS Feed"
        elif "atom.xml" in href or "/atom" in href:
            return "Atom Feed"

        return ""

    def _fix_search_inputs(self, soup) -> bool:
        """Fix search input elements without associated labels."""
        modified = False
        search_inputs = soup.find_all("input", {"type": "search"})

        for input_tag in search_inputs:
            if not input_tag.get("aria-label") and not input_tag.get("id"):
                # Generate an ID for the input
                input_id = f"search-{id(input_tag)}"
                input_tag["id"] = input_id
                modified = True
                logger.debug(f"Added ID to search input: {input_id}")

            if not input_tag.get("aria-label"):
                # Try to find an associated label
                label = self._find_associated_label(input_tag)
                if label:
                    input_tag["aria-label"] = label
                    modified = True
                    logger.debug(
                        f"Added aria-label to search input from label: {label}"
                    )

        return modified

    def _find_associated_label(self, input_tag) -> str:
        """Find an associated label for an input element.

        Args:
            input_tag: BeautifulSoup input element

        Returns:
            Associated label text, or empty string if none found
        """
        # Check for <label> elements with for attribute matching the input ID
        label = input_tag.find_previous("label", for_=input_tag.get("id"))
        if label and label.get_text(strip=True):
            return label.get_text(strip=True)

        # Check for nearby <label> elements
        label = input_tag.find_previous("label")
        if label and label.get_text(strip=True):
            return label.get_text(strip=True)

        return ""

    def _fix_table_accessibility(self, soup) -> bool:
        """Fix accessibility issues in tables."""
        modified = False
        tables = soup.find_all("table")

        for table in tables:
            # Ensure table has a caption or aria-label
            if not table.find("caption") and not table.get("aria-label"):
                # Try to find a heading before the table
                prev = table.find_previous(["h1", "h2", "h3", "h4", "h5", "h6"])
                if prev:
                    caption_text = prev.get_text(strip=True)
                    table["aria-label"] = f"Table: {caption_text}"
                    modified = True
                    logger.debug(f"Added aria-label to table: {caption_text}")
                else:
                    table["aria-label"] = "Data table"
                    modified = True
                    logger.debug("Added generic aria-label to table")

            # Check for proper header markup
            thead = table.find("thead")
            if not thead:
                # Look for first row that might be headers
                first_row = table.find("tr")
                if first_row:
                    cells = first_row.find_all("td")
                    # If first row has only td elements, they might be headers
                    if cells and not first_row.find_all("th"):
                        # Check if cells contain header-like content (short text, bold, etc.)
                        likely_headers = all(
                            len(cell.get_text(strip=True)) < 50 for cell in cells
                        )
                        if likely_headers:
                            # Convert td to th with scope
                            for cell in cells:
                                cell.name = "th"
                                if not cell.get("scope"):
                                    cell["scope"] = "col"
                            modified = True
                            logger.debug("Converted first row cells to header cells")

        return modified

    def _fix_redundant_links(self, soup) -> bool:
        """Fix adjacent redundant links (same URL, next to each other)."""
        modified = False

        # Find Quarto listing items with image and text links
        listing_items = soup.find_all("div", class_="quarto-post")
        for item in listing_items:
            # Find image link in thumbnail div
            thumbnail = item.find("div", class_="thumbnail")
            if thumbnail:
                img_link = thumbnail.find("a")
                if img_link:
                    img_href = img_link.get("href", "")

                    # Find title link in body div
                    body = item.find("div", class_="body")
                    if body:
                        title_link = body.find("a")
                        if title_link and title_link.get("href") == img_href:
                            # Same URL - make image link decorative
                            if not img_link.get("aria-hidden"):
                                img_link["aria-hidden"] = "true"
                                img_link["tabindex"] = "-1"
                                modified = True
                                logger.debug(
                                    f"Hidden redundant image link in listing: {img_href}"
                                )

        # Also check for traditional adjacent links
        links = soup.find_all("a")
        for i in range(len(links) - 1):
            current_link = links[i]
            next_link = links[i + 1]

            # Check if they're adjacent in the DOM
            if current_link.next_sibling == next_link or (
                current_link.next_sibling
                and current_link.next_sibling.next_sibling == next_link
            ):
                current_href = current_link.get("href", "")
                next_href = next_link.get("href", "")

                # If same URL and adjacent, check if one is an image link
                if current_href == next_href and current_href:
                    current_has_img = current_link.find("img") is not None
                    next_has_img = next_link.find("img") is not None

                    # Only flag, don't remove automatically (might be intentional)
                    if current_has_img and not next_has_img:
                        # Image link followed by text link - common pattern, add aria-hidden to image
                        if not current_link.get("aria-hidden"):
                            current_link["aria-hidden"] = "true"
                            current_link["tabindex"] = "-1"
                            modified = True
                            logger.debug(
                                f"Added aria-hidden to redundant image link: {current_href}"
                            )
                    elif not current_has_img and next_has_img:
                        # Text link followed by image link
                        if not next_link.get("aria-hidden"):
                            next_link["aria-hidden"] = "true"
                            next_link["tabindex"] = "-1"
                            modified = True
                            logger.debug(
                                f"Added aria-hidden to redundant image link: {current_href}"
                            )

        return modified

    def _fix_listing_grids(self, soup) -> bool:
        """Fix accessibility issues in Quarto listing grids."""
        modified = False

        # Find all divs that might be listing grids (based on class or other attributes)
        grids = soup.find_all("div", class_="listing-grid")

        for grid in grids:
            # Ensure grid has an aria-label or role="grid"
            if not grid.get("aria-label") and not grid.get("role") == "grid":
                # Try to find a heading or label for the grid
                label = grid.find_previous(
                    ["h1", "h2", "h3", "h4", "h5", "h6", "label"]
                )
                if label:
                    grid["aria-label"] = f"Listing grid: {label.get_text(strip=True)}"
                    modified = True
                    logger.debug(
                        f"Added aria-label to listing grid: {label.get_text(strip=True)}"
                    )
                else:
                    grid["aria-label"] = "Listing grid"
                    modified = True
                    logger.debug("Added generic aria-label to listing grid")

            # Ensure all items in the grid have accessible names
            items = grid.find_all(["a", "button", "div"], recursive=False)
            for item in items:
                if not item.get("aria-label") and not item.get("title"):
                    # Try to generate a label from text content or context
                    label = self._generate_listing_item_label(item)
                    if label:
                        item["aria-label"] = label
                        modified = True
                        logger.debug(f"Added aria-label to listing grid item: {label}")

        return modified

    def _generate_listing_item_label(self, item) -> str:
        """Generate aria-label for a listing grid item.

        Args:
            item: BeautifulSoup item element

        Returns:
            Generated label
        """
        # Try to get from title
        if item.get("title"):
            return item["title"]

        # Try to get from surrounding text
        text = item.get_text(strip=True)
        if text:
            return text

        # If item is an image link, describe the image
        img = item.find("img")
        if img and img.get("alt"):
            return f"Image: {img['alt']}"

        return ""


    def _fix_listing_item_links(self, soup) -> bool:
        """Fix accessibility issues with listing item links."""
        modified = False

        # Find listing items that have redundant image + text links
        listing_items = soup.find_all("div", class_="listing-item")

        for item in listing_items:
            links = item.find_all("a")

            # Check for adjacent image + text links with same href
            for i in range(len(links) - 1):
                current = links[i]
                next_link = links[i + 1]

                if current.get("href") == next_link.get("href"):
                    current_img = current.find("img")
                    next_img = next_link.find("img")

                    # If one has image and other has text, hide the image link
                    if current_img and not next_img:
                        # Current is image link, next is text link
                        if not current.get("aria-hidden"):
                            current["aria-hidden"] = "true"
                            current["tabindex"] = "-1"
                            modified = True
                    elif next_img and not current_img:
                        # Next is image link, current is text link
                        if not next_link.get("aria-hidden"):
                            next_link["aria-hidden"] = "true"
                            next_link["tabindex"] = "-1"
                            modified = True

        return modified

    def _fix_skip_links(self, soup) -> bool:
        """Add skip navigation link if missing."""
        modified = False

        # Check if skip link already exists
        skip_link = soup.find("a", href="#quarto-document-content")
        if skip_link:
            return False

        # Add skip link at the beginning of body
        body = soup.find("body")
        if body:
            # Create skip link
            skip_link = soup.new_tag(
                "a",
                href="#quarto-document-content",
                **{
                    "class": "visually-hidden-focusable",
                    "style": "position: absolute; top: -40px; left: 0; z-index: 9999;",
                },
            )
            skip_link.string = "Skip to main content"

            # Insert as first child of body
            body.insert(0, skip_link)
            modified = True
            logger.debug("Added skip navigation link")

        return modified

    def _fix_main_landmark(self, soup) -> bool:
        """Ensure page has a main landmark."""
        modified = False

        # Check if main element exists
        main = soup.find("main")
        if main:
            return False

        # Look for content div that should be main
        content_div = soup.find("div", id="quarto-document-content")
        if content_div and content_div.name != "main":
            content_div.name = "main"
            modified = True
            logger.debug("Converted content div to main element")

        return modified


def fix_accessibility(html_files: List[Path]) -> None:
    """Fix accessibility issues in HTML files.

    Args:
        html_files: List of HTML file paths to process
    """
    project_root = Path.cwd()
    fs = FileSystem(project_root)
    html_processor = HtmlProcessor()
    fixer = AccessibilityFixer(fs, html_processor)

    fixed_count = 0
    for html_file in html_files:
        if fixer.fix_html_file(html_file):
            fixed_count += 1

    logger.info(f"Fixed accessibility issues in {fixed_count} file(s)")


def main():
    """CLI entry point."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: fix_accessibility.py <html_file1> [html_file2 ...]")
        sys.exit(1)

    html_files = [Path(f) for f in sys.argv[1:]]
    fix_accessibility(html_files)


if __name__ == "__main__":
    main()
