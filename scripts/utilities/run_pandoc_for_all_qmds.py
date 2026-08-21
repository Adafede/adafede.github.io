"""Pandoc PDF generator for QMD posts.

Converts markdown files to PDF using Pandoc with bibliography processing
and CiTO filters.
"""

import subprocess
import sys
from pathlib import Path

# Add project root to path so `scripts` is importable as a package
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir))

from scripts.infrastructure import FileSystem, get_logger
from scripts.services.pdf_service import fix_image_paths_in_md

logger = get_logger(__name__)

POSTS_DIR = Path("posts")
SITE_POSTS_DIR = Path("_site/posts")
BIBLIOGRAPHY_FILE = Path("posts/references.bib")
CSL_FILE = Path("journal-of-cheminformatics.csl")

PANDOC_FILTERS = [
    Path("filters/extract-cito.lua"),
    Path("filters/insert-cito-in-ref.lua"),
]


def build_pandoc_command(md_path: Path, pdf_path: Path) -> list[str]:
    """Build the Pandoc command-line for converting *md_path* to *pdf_path*."""
    return [
        "pandoc",
        str(md_path),
        "--to=pdf",
        f"--bibliography={BIBLIOGRAPHY_FILE}",
        f"--lua-filter={PANDOC_FILTERS[0]}",
        "--citeproc",
        f"--lua-filter={PANDOC_FILTERS[1]}",
        f"--csl={CSL_FILE}",
        "-o",
        str(pdf_path),
    ]


def convert_md_to_pdf(md_path: Path, pdf_path: Path) -> bool:
    """Run Pandoc to convert *md_path* to *pdf_path*. Returns ``True`` on success."""
    cmd = build_pandoc_command(md_path, pdf_path)
    logger.debug(f"Running: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info(f"✓ Generated PDF: {pdf_path.name}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"✗ Pandoc failed for {md_path.name}: {e.stderr}")
        return False
    except FileNotFoundError:
        logger.error("Pandoc not found. Please install Pandoc.")
        return False


def run_pandoc_for_all_qmds() -> None:
    """Convert all QMD posts' generated Markdown to PDF via Pandoc."""
    project_root = Path.cwd()
    fs = FileSystem(project_root)

    qmd_files = fs.find_posts("posts")
    if not qmd_files:
        logger.warning(f"No QMD files found in {POSTS_DIR}")
        return

    logger.info(f"Converting {len(qmd_files)} posts to PDF")

    if not fs.exists(BIBLIOGRAPHY_FILE):
        logger.warning(f"Bibliography not found: {BIBLIOGRAPHY_FILE}")
    if not fs.exists(CSL_FILE):
        logger.warning(f"CSL file not found: {CSL_FILE}")

    success_count = 0
    skip_count = 0
    fail_count = 0

    for qmd_file in qmd_files:
        base_name = qmd_file.stem
        md_path = SITE_POSTS_DIR / f"{base_name}.md"
        pdf_path = SITE_POSTS_DIR / f"{base_name}.pdf"

        if not fs.exists(md_path):
            logger.debug(f"Skipping {qmd_file.name}: markdown not found at {md_path}")
            skip_count += 1
            continue

        # Fix ../images/... → _site/images/... before converting
        fix_image_paths_in_md(md_path)

        if convert_md_to_pdf(md_path, pdf_path):
            success_count += 1
        else:
            fail_count += 1

    logger.info("=" * 60)
    logger.info("PDF Generation Summary:")
    logger.info(f"  Success: {success_count}")
    logger.info(f"  Skipped: {skip_count} (markdown not found)")
    logger.info(f"  Failed:  {fail_count}")
    logger.info("=" * 60)


if __name__ == "__main__":
    run_pandoc_for_all_qmds()
