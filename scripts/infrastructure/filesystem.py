"""File system operations and path utilities."""

from __future__ import annotations

from pathlib import Path

from .logger import get_logger

logger = get_logger(__name__)


class FileSystem:
    """Provides file system operations with semantic naming."""

    def __init__(self, root: Path):
        """Initialize with project root directory.

        Args:
            root: Project root directory
        """
        self.root = Path(root).resolve()

    def find_posts(self, posts_dir: str = "posts") -> list[Path]:
        """Find all post QMD files with date-prefixed naming.

        Args:
            posts_dir: Directory containing posts (relative to root)

        Returns:
            List of Path objects for dated post files
        """
        pattern = "20[0-9][0-9]-[01][0-9]-[0-3][0-9]_*.qmd"
        posts_path = self.root / posts_dir
        files = list(posts_path.glob(pattern))
        logger.debug(f"Found {len(files)} posts in {posts_path}")
        return files

    def find_qmd_files(self, pattern: str) -> list[Path]:
        """Find QMD files matching a glob pattern.

        Args:
            pattern: Glob pattern relative to root (e.g., "articles/**/*.qmd")

        Returns:
            List of matching Path objects
        """
        files = list(self.root.glob(pattern))
        logger.debug(f"Found {len(files)} files matching {pattern}")
        return files

    def get_html_path(self, qmd_path: Path, site_dir: str = "_site") -> Path:
        """Get corresponding HTML path for a QMD file.

        Args:
            qmd_path: Path to QMD file
            site_dir: Output directory name

        Returns:
            Path to generated HTML file
        """
        # Calculate relative path from root
        try:
            rel_path = qmd_path.relative_to(self.root)
        except ValueError:
            # If qmd_path is not relative to root, assume it's already relative
            rel_path = qmd_path

        # Convert to HTML path in site directory
        html_rel = rel_path.with_suffix(".html")
        html_path = self.root / site_dir / html_rel

        return html_path

    def read_text(self, path: Path, encoding: str = "utf-8") -> str:
        """Read text file with error handling.

        Args:
            path: File path
            encoding: Text encoding

        Returns:
            File contents as string

        Raises:
            FileNotFoundError: If file doesn't exist
            UnicodeDecodeError: If encoding fails
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        return path.read_text(encoding=encoding)

    def write_text(
        self,
        path: Path,
        content: str,
        encoding: str = "utf-8",
        create_parents: bool = True,
    ) -> None:
        """Write text to file with error handling.

        Args:
            path: File path
            content: Text content to write
            encoding: Text encoding
            create_parents: Create parent directories if they don't exist
        """
        path = Path(path)

        if create_parents:
            path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(content, encoding=encoding)
        logger.debug(f"Wrote {len(content)} chars to {path}")

    def exists(self, path: Path) -> bool:
        """Check if path exists.

        Args:
            path: Path to check

        Returns:
            True if path exists
        """
        return Path(path).exists()

    def extract_date_from_filename(self, path: Path) -> str:
        """Extract date from filename (YYYY-MM-DD prefix).

        Args:
            path: Path with date prefix

        Returns:
            Date string (YYYY-MM-DD)
        """
        return path.stem.split("_")[0]
