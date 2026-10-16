"""Markdown image-path fixing for Pandoc PDF generation.

During ``quarto render``, the Markdown Pandoc consumes lives in ``_site/posts/``
while the images live in ``_site/images/``, so an ``../images/foo.png`` reference
— correct relative to the *source* post — resolves to ``_site/posts/images/``,
which does not exist.  This helper rewrites those references to ``_site/images/``,
creating a ``.bak`` backup first.
"""

import re
import shutil
from pathlib import Path

from scripts.infrastructure.logger import get_logger

logger = get_logger(__name__)

_MD_IMG_RE = re.compile(
    r"!\[([^\]]*)\]\(\s*\.\./images/([^\)\s]+)(?:\s+\"[^\"]*\")?\s*\)",
)


def fix_image_paths_in_md(md_path: Path) -> None:
    """Rewrite ``../images/`` Markdown links to ``_site/images/`` in-place.

    Only rewrites when the file actually contains such references.  A ``.bak``
    backup is created before the first modification.

    Args:
        md_path: Path to the Markdown file to rewrite. Must already exist; an
            unreadable or missing file is logged at debug level and skipped,
            because the caller iterates over posts that may or may not have
            been rendered yet.
    """
    try:
        text = md_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        logger.debug(f"Could not read {md_path} for path-fix")
        return

    new_text, n = _MD_IMG_RE.subn(r"![\1](_site/images/\2)", text)

    if n > 0 and new_text != text:
        bak = md_path.with_suffix(md_path.suffix + ".bak")
        try:
            _ = shutil.copy2(md_path, bak)
        except OSError:
            logger.warning(f"Could not create backup for {md_path}")
        try:
            _ = md_path.write_text(new_text, encoding="utf-8")
            logger.info(f"Rewrote {n} Markdown image path(s) in {md_path}")
        except OSError as e:
            logger.error(f"Failed to write fixed markdown {md_path}: {e}")
    else:
        logger.debug(f"No Markdown image path fixes required for {md_path}")
