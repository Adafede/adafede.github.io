"""Pre-render script for Quarto site generation.

Runs before Quarto renders the site to update metadata in QMD files.
"""

import sys
from pathlib import Path

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import LOG_LEVEL, PROJECT_ROOT
from infrastructure import FileSystem, get_logger, setup_logging
from services import MetadataService

# Setup logging
setup_logging(level=LOG_LEVEL)
logger = get_logger(__name__)


def prerender() -> None:
    """Main pre-render orchestration."""
    logger.info("=" * 80)
    logger.info("Starting pre-render processing")
    logger.info("=" * 80)

    try:
        # Initialize infrastructure and services
        fs = FileSystem(PROJECT_ROOT)
        metadata_service = MetadataService(fs)

        # Find all posts
        posts = fs.find_posts("posts")
        logger.info(f"Found {len(posts)} post(s) to process")

        if posts:
            # Update metadata (dates, DOIs, etc.)
            modified_count = sum(
                1
                for post in posts
                if metadata_service.update_post_metadata(post, generate_doi=True)
            )
            logger.info(f"Updated metadata for {modified_count} post(s)")
        else:
            logger.warning("No posts found for processing")

        logger.info("=" * 80)
        logger.info("Pre-render processing completed successfully")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Pre-render failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    prerender()
