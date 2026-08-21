"""Site-wide paths and constants for the post-processing pipeline.

Everything here is imported by ``prerender.py`` / ``postrender.py`` and the
utility scripts.  Constants that are only needed by a single module live in
that module rather than here, to avoid dead defaults drifting out of sync.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
SITE_DIR = PROJECT_ROOT / "_site"

# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------

RSS_FILE = SITE_DIR / "posts.xml"
JSON_FEED_FILE = SITE_DIR / "posts.json"

# ---------------------------------------------------------------------------
# Glob patterns for QMD files grouped by content type
# ---------------------------------------------------------------------------

QMD_PATTERNS = {
    "articles": "articles/**/*.qmd",
    "talks": "talks/*.qmd",
    "teaching": "teaching/*.qmd",
    "posts": "posts/*.qmd",
}

# ---------------------------------------------------------------------------
# CiTO (Citation Typing Ontology) annotation constants
# ---------------------------------------------------------------------------

REFS_CONTAINER_ID = "refs"
CSL_ENTRY_CLASS = "csl-entry"
CITO_SPAN_CLASS = "cito"
REF_ID_PREFIX = "ref-"

# ---------------------------------------------------------------------------
# DOI
# ---------------------------------------------------------------------------

DOI_URL_PREFIX = "https://doi.org/"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_LEVEL = "INFO"
