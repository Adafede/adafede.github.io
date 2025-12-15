"""
Post-render script for Quarto site generation.

This script runs after Quarto renders the site and performs:
- Pandoc conversion for PDFs
- CiTO annotation injection
- ROR affiliation linking
- RSS/JSON feed generation
- Semantic annotation enhancement
"""

import logging
import sys
from pathlib import Path
from typing import List

from convert_rss_to_json_feed import convert_rss_to_json_feed
from inject_author_links import inject_author_links
from inject_cito_annotations_in_html import inject_cito_annotations_in_html
from inject_cito_annotations_in_rss import inject_cito_annotations_in_rss
from inject_doi_in_rss import inject_doi_in_rss
from inject_ror_in_html import inject_ror_in_html
from merge_citos import merge_citos
from parse_citos_from_qmd import parse_citos_from_qmd
from process_qmd_directory import process_qmd_directory
from run_pandoc_for_all_qmds import run_pandoc_for_all_qmds

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

SITE_DIR = Path("_site")
POSTS_DIR = Path("posts")
RSS_FILE = SITE_DIR / "posts.xml"
JSON_FEED_FILE = SITE_DIR / "posts.json"

# Directories to process
QMD_PATTERNS = {
    "articles": "articles/**/*.qmd",
    "talks": "talks/*.qmd",
    "teaching": "teaching/*.qmd",
}


# ============================================================================
# PROCESSING FUNCTIONS
# ============================================================================


def process_articles_talks_teaching() -> None:
    """Process articles, talks, and teaching directories."""
    logger.info("Processing articles, talks, and teaching directories")

    for name, pattern in QMD_PATTERNS.items():
        try:
            logger.info(f"Processing {name}: {pattern}")
            process_qmd_directory(qmd_glob=pattern)
        except Exception as e:
            logger.error(f"Failed to process {name}: {e}", exc_info=True)


def collect_post_qmd_files() -> List[Path]:
    """Collect all QMD files from posts directory.

    Returns:
        List of Path objects for post QMD files
    """
    qmd_files = list(POSTS_DIR.glob("*.qmd"))
    logger.info(f"Found {len(qmd_files)} post QMD files")
    return qmd_files


def process_cito_annotations(post_qmds: List[Path]) -> dict:
    """Parse and merge CiTO annotations from all posts.

    Args:
        post_qmds: List of post QMD file paths

    Returns:
        Dictionary mapping citation IDs to sorted lists of CiTO properties
    """
    logger.info("Parsing CiTO annotations from posts")

    try:
        all_cito_dicts = [parse_citos_from_qmd(qmd) for qmd in post_qmds]
        merged = merge_citos(all_cito_dicts)
        citation_properties = {k: sorted(v) for k, v in merged.items()}

        logger.info(f"Merged CiTO annotations for {len(citation_properties)} citations")
        return citation_properties
    except Exception as e:
        logger.error(f"Failed to process CiTO annotations: {e}", exc_info=True)
        return {}


def inject_html_annotations(post_qmds: List[Path], citation_properties: dict) -> None:
    """Inject CiTO and ROR annotations into HTML files.

    Args:
        post_qmds: List of post QMD file paths
        citation_properties: Dictionary of citation properties
    """
    logger.info("Injecting annotations into HTML files")

    for qmd_file in post_qmds:
        base_name = qmd_file.stem
        html_file = SITE_DIR / "posts" / f"{base_name}.html"

        if not html_file.exists():
            logger.warning(f"HTML not found for {qmd_file.name} at {html_file}")
            continue

        try:
            # Inject CiTO annotations
            inject_cito_annotations_in_html(
                html_path=html_file,
                citation_properties=citation_properties,
            )

            # Inject ROR affiliations
            inject_ror_in_html(
                qmd_path=qmd_file,
                html_path=html_file,
            )

            # Inject author ORCID icons and Scholia links
            inject_author_links(
                qmd_path=qmd_file,
                html_path=html_file,
            )
        except Exception as e:
            logger.error(
                f"Failed to inject annotations for {qmd_file.name}: {e}",
                exc_info=True,
            )


def process_rss_and_feeds(post_qmds: List[Path], citation_properties: dict) -> None:
    """Process RSS feed and convert to JSON feed.

    Args:
        post_qmds: List of post QMD file paths
        citation_properties: Dictionary of citation properties
    """
    if not RSS_FILE.exists():
        logger.warning(f"RSS file not found at {RSS_FILE}")
        return

    logger.info("Processing RSS and JSON feeds")

    try:
        # Inject DOIs into RSS
        inject_doi_in_rss(rss_path=RSS_FILE, qmd_files=post_qmds)

        # Inject CiTO annotations into RSS
        inject_cito_annotations_in_rss(
            rss_path=RSS_FILE,
            citation_properties=citation_properties,
        )

        # Convert to JSON Feed
        convert_rss_to_json_feed(
            rss_path=RSS_FILE,
            json_feed_path=JSON_FEED_FILE,
        )

        logger.info("RSS and JSON feeds processed successfully")
    except Exception as e:
        logger.error(f"Failed to process feeds: {e}", exc_info=True)


# ============================================================================
# MAIN ORCHESTRATION
# ============================================================================


def postrender() -> None:
    """Main post-render orchestration function."""
    logger.info("=" * 80)
    logger.info("Starting post-render processing")
    logger.info("=" * 80)

    try:
        # Step 1: Run Pandoc conversion for PDFs
        logger.info("Step 1: Running Pandoc conversions")
        run_pandoc_for_all_qmds()

        # Step 2: Process articles, talks, and teaching
        logger.info("Step 2: Processing articles, talks, and teaching")
        process_articles_talks_teaching()

        # Step 3: Process posts
        logger.info("Step 3: Processing posts")
        post_qmds = collect_post_qmd_files()

        if not post_qmds:
            logger.warning("No post QMD files found - skipping post processing")
        else:
            citation_properties = process_cito_annotations(post_qmds)
            inject_html_annotations(post_qmds, citation_properties)
            process_rss_and_feeds(post_qmds, citation_properties)

        logger.info("=" * 80)
        logger.info("Post-render processing completed successfully")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Post-render failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    postrender()
