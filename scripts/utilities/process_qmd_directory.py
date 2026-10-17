"""
QMD directory processor.

Processes QMD files in a directory pattern and injects ROR links and
author metadata (ORCID icons, Scholia links) into corresponding HTML files.
Uses the refactored service architecture.
"""

import sys
from pathlib import Path

# Add project root to path so `scripts` is importable as a package
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.infrastructure import FileSystem, HtmlProcessor, YamlLoader, get_logger
from scripts.services import AuthorService, RorService

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
    # Anchored to the project root rather than the process CWD, so the same
    # files are found no matter where the script is invoked from.
    qmd_files = sorted(PROJECT_ROOT.glob(qmd_glob))

    if not qmd_files:
        logger.warning(f"No QMD files found matching pattern: {qmd_glob}")
        return

    logger.info(f"Processing {len(qmd_files)} QMD files from {qmd_glob}")

    # The project root, not the working directory. Quarto happens to invoke
    # this from the project root, so a CWD-relative path works there and
    # nowhere else.
    fs = FileSystem(PROJECT_ROOT)
    html_processor = HtmlProcessor()
    yaml_loader = YamlLoader()

    ror_service = RorService(fs, html_processor, yaml_loader)
    author_service = AuthorService(fs, html_processor, yaml_loader)

    processed = 0
    missing = 0

    for qmd_file in qmd_files:
        qmd_path = Path(qmd_file).resolve()

        # The HTML sits at the same place in the Quarto output tree. Anchored to
        # the project root for the same reason the glob's matches are resolved:
        # a relative path here resolves against wherever the process was
        # started.
        try:
            rel_path = qmd_path.relative_to(PROJECT_ROOT)
        except ValueError:
            # The pattern matched something outside the project. Injecting into
            # it would mean writing outside the site.
            logger.warning(f"Skipping {qmd_file}: not under {PROJECT_ROOT}")
            continue
        html_path = PROJECT_ROOT / "_site" / rel_path.with_suffix(".html")

        if html_path.exists():
            try:
                # Inject ROR affiliations
                _ = ror_service.inject_into_html(qmd_path, html_path)

                # Inject author ORCID icons and Scholia links
                _ = author_service.inject_into_html(qmd_path, html_path)

                processed += 1
            except Exception:
                logger.exception(f"Failed to process {qmd_path.name}")
        else:
            logger.warning(
                f"HTML not found for {qmd_path.name} at "
                f"{html_path.relative_to(PROJECT_ROOT)}",
            )
            missing += 1

    logger.info(f"Processed {processed} files, {missing} HTML files missing")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: process_qmd_directory.py <glob_pattern>")
        print("Examples:")
        print("  process_qmd_directory.py 'posts/*.qmd'")
        print("  process_qmd_directory.py 'articles/**/*.qmd'")
        sys.exit(1)

    process_qmd_directory(sys.argv[1])
