"""Post-render script for Quarto site generation.

Runs after Quarto renders the site to inject semantic annotations.
"""

import sys
from pathlib import Path
from typing import List

from infrastructure import (
    FileSystem,
    HtmlProcessor,
    YamlLoader,
    get_logger,
    setup_logging,
)
from services import AuthorService, CitoService, RorService
from utilities import (
    convert_rss_to_json_feed,
    inject_cito_annotations_in_rss,
    inject_doi_in_rss,
    process_qmd_directory,
    run_pandoc_for_all_qmds,
)

# Setup logging
setup_logging(level="INFO")
logger = get_logger(__name__)

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
SITE_DIR = PROJECT_ROOT / "_site"
POSTS_DIR = PROJECT_ROOT / "posts"
RSS_FILE = SITE_DIR / "posts.xml"
JSON_FEED_FILE = SITE_DIR / "posts.json"

# Directories to process
QMD_PATTERNS = {
    "articles": "articles/**/*.qmd",
    "talks": "talks/*.qmd",
    "teaching": "teaching/*.qmd",
}


def process_articles_talks_teaching() -> None:
    """Process articles, talks, and teaching directories."""
    logger.info("Processing articles, talks, and teaching directories")

    for name, pattern in QMD_PATTERNS.items():
        try:
            logger.info(f"Processing {name}: {pattern}")
            process_qmd_directory(qmd_glob=pattern)
        except Exception as e:
            logger.error(f"Failed to process {name}: {e}", exc_info=True)


def process_posts(
    fs: FileSystem,
    cito_service: CitoService,
    author_service: AuthorService,
    ror_service: RorService,
    yaml_loader: YamlLoader,
) -> None:
    """Process all posts with CiTO, author, and ROR annotations.

    Args:
        fs: FileSystem instance
        cito_service: CitoService instance
        author_service: AuthorService instance
        ror_service: RorService instance
        yaml_loader: YamlLoader instance
    """
    logger.info("Processing posts")

    # Find all post QMD files
    post_qmds = fs.find_posts("posts")
    logger.info(f"Found {len(post_qmds)} post QMD files")

    if not post_qmds:
        logger.warning("No post QMD files found - skipping post processing")
        return

    # Parse CiTO annotations from all posts
    logger.info("Parsing CiTO annotations from posts")
    all_citations = [cito_service.parse_citations_from_qmd(qmd) for qmd in post_qmds]
    citation_properties = cito_service.merge_citations(all_citations)
    logger.info(f"Merged CiTO annotations for {len(citation_properties)} citations")

    # Inject annotations into HTML files
    logger.info("Injecting annotations into HTML files")
    for qmd_file in post_qmds:
        base_name = qmd_file.stem
        html_file = SITE_DIR / "posts" / f"{base_name}.html"

        if not html_file.exists():
            logger.warning(f"HTML not found for {qmd_file.name} at {html_file}")
            continue

        try:
            # Inject CiTO annotations
            cito_service.inject_into_html(html_file, citation_properties)

            # Inject ROR affiliations
            ror_service.inject_into_html(qmd_file, html_file)

            # Inject author ORCID icons and Scholia links
            author_service.inject_into_html(qmd_file, html_file)

        except Exception as e:
            logger.error(f"Failed to inject annotations for {qmd_file.name}: {e}",
                        exc_info=True)

    # Process RSS and feeds
    process_rss_and_feeds(post_qmds, citation_properties, yaml_loader)


def process_rss_and_feeds(
    post_qmds: List[Path],
    citation_properties: dict,
    yaml_loader: YamlLoader
) -> None:
    """Process RSS feed and convert to JSON feed.

    Args:
        post_qmds: List of post QMD file paths
        citation_properties: Dictionary of citation properties
        yaml_loader: YamlLoader instance for DOI extraction
    """
    if not RSS_FILE.exists():
        logger.warning(f"RSS file not found at {RSS_FILE}")
        return

    logger.info("Processing RSS and JSON feeds")

    try:
        # Inject DOIs into RSS
        inject_doi_in_rss(
            rss_path=RSS_FILE, qmd_files=post_qmds, yaml_loader=yaml_loader
        )

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


def postrender() -> None:
    """Main post-render orchestration function."""
    logger.info("=" * 80)
    logger.info("Starting post-render processing")
    logger.info("=" * 80)

    try:
        # Initialize infrastructure
        fs = FileSystem(PROJECT_ROOT)
        html_processor = HtmlProcessor()
        yaml_loader = YamlLoader()

        # Initialize services
        cito_service = CitoService(fs, html_processor)
        author_service = AuthorService(fs, html_processor, yaml_loader)
        ror_service = RorService(fs, html_processor, yaml_loader)

        # Step 1: Run Pandoc conversion for PDFs
        logger.info("Step 1: Running Pandoc conversions")
        run_pandoc_for_all_qmds()

        # Step 2: Process articles, talks, and teaching
        logger.info("Step 2: Processing articles, talks, and teaching")
        process_articles_talks_teaching()

        # Step 3: Process posts
        logger.info("Step 3: Processing posts")
        process_posts(fs, cito_service, author_service, ror_service, yaml_loader)

        logger.info("=" * 80)
        logger.info("Post-render processing completed successfully")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Post-render failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    postrender()
