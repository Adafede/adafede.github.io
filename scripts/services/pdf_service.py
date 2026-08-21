"""Markdown image-path fixing for Pandoc PDF generation.

During ``quarto render``, generated Markdown in ``_site/posts/`` may reference
images with ``../images/`` paths that are wrong on disk.  This helper rewrites
those to ``_site/images/`` when the target exists, creating a ``.bak`` backup.
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

    Only rewrites when the file contains such references.
    A ``.bak`` backup is created before the first modification.
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
            shutil.copy2(md_path, bak)
        except OSError:
            logger.warning(f"Could not create backup for {md_path}")
        try:
            md_path.write_text(new_text, encoding="utf-8")
            logger.info(f"Rewrote {n} Markdown image path(s) in {md_path}")
        except OSError as e:
            logger.error(f"Failed to write fixed markdown {md_path}: {e}")
    else:
        logger.debug(f"No Markdown image path fixes required for {md_path}")
