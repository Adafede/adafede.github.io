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
        """Check and log heading hierarchy issues."""
        # This is more complex and might require manual review
        # For now, just log warnings
        headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])

        if not headings:
            return False

        prev_level = 0
        for heading in headings:
            level = int(heading.name[1])
            if prev_level > 0 and level > prev_level + 1:
                logger.warning(
                    f"Heading hierarchy skip detected: {heading.name} after h{prev_level}"
                )
            prev_level = level

        return False


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
