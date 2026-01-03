"""
QMD directory processor.

Processes QMD files in a directory pattern and injects ROR links and
author metadata (ORCID icons, Scholia links) into corresponding HTML files.
Uses the refactored service architecture.
"""

import glob
import sys
from pathlib import Path

# Add parent directory to path for infrastructure imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure import FileSystem, HtmlProcessor, YamlLoader, get_logger
from services import AuthorService, RorService

logger = get_logger(__name__)


def process_qmd_directory(qmd_glob: str) -> None:
    """Process QMD files matching a glob pattern.

    For each QMD file, finds the corresponding HTML file in _site directory
    and injects ROR links and author metadata using the service architecture.

    Args:
        qmd_glob: Glob pattern for QMD files (e.g., "articles/**/*.qmd")

    Example:
        >>> process_qmd_directory("posts/*.qmd")
        >>> process_qmd_directory("articles/**/*.qmd")
    """
    # Extract root directory from glob pattern
    root_dir = qmd_glob.split("*", 1)[0].rstrip("/")

    # Find all matching QMD files
    qmd_files = glob.glob(qmd_glob, recursive=True)

    if not qmd_files:
        logger.warning(f"No QMD files found matching pattern: {qmd_glob}")
        return

    logger.info(f"Processing {len(qmd_files)} QMD files from {qmd_glob}")

    # Initialize services
    project_root = Path.cwd()
    fs = FileSystem(project_root)
    html_processor = HtmlProcessor()
    yaml_loader = YamlLoader()

    ror_service = RorService(fs, html_processor, yaml_loader)
    author_service = AuthorService(fs, html_processor, yaml_loader)

    processed = 0
    missing = 0

    for qmd_file in qmd_files:
        qmd_path = Path(qmd_file)

        # Calculate relative path and corresponding HTML path
        rel_path = qmd_path.relative_to(root_dir)
        rel_html_path = rel_path.with_suffix(".html")
        html_path = Path("_site") / root_dir / rel_html_path

        if html_path.exists():
            try:
                # Inject ROR affiliations
                ror_service.inject_into_html(qmd_path, html_path)

                # Inject author ORCID icons and Scholia links
                author_service.inject_into_html(qmd_path, html_path)

                processed += 1
            except Exception as e:
                logger.error(f"Failed to process {qmd_file}: {e}", exc_info=True)
        else:
            logger.warning(f"HTML not found for {qmd_file} at {html_path}")
            missing += 1

    logger.info(f"Processed {processed} files, {missing} HTML files missing")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: process_qmd_directory.py <glob_pattern>")
        print("Examples:")
        print("  process_qmd_directory.py 'posts/*.qmd'")
        print("  process_qmd_directory.py 'articles/**/*.qmd'")
        sys.exit(1)

    process_qmd_directory(sys.argv[1])
