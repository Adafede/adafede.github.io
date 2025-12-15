"""
Configuration module for Quarto semantic web processing scripts.

Centralizes all configuration values, paths, and constants used across
the post-processing pipeline.
"""

from pathlib import Path

# ============================================================================
# DIRECTORY PATHS
# ============================================================================

# Root directories
PROJECT_ROOT = Path(__file__).parent.parent
SITE_DIR = PROJECT_ROOT / "_site"
POSTS_DIR = PROJECT_ROOT / "posts"
ARTICLES_DIR = PROJECT_ROOT / "articles"
TALKS_DIR = PROJECT_ROOT / "talks"
TEACHING_DIR = PROJECT_ROOT / "teaching"
FILTERS_DIR = PROJECT_ROOT / "filters"

# Output directories
SITE_POSTS_DIR = SITE_DIR / "posts"
SITE_ARTICLES_DIR = SITE_DIR / "articles"
SITE_TALKS_DIR = SITE_DIR / "talks"
SITE_TEACHING_DIR = SITE_DIR / "teaching"


# ============================================================================
# FILE PATHS
# ============================================================================

# Bibliography and citation files
BIBLIOGRAPHY_FILE = POSTS_DIR / "references.bib"
CSL_FILE = PROJECT_ROOT / "journal-of-cheminformatics.csl"

# RSS and feed files
RSS_FILE = SITE_DIR / "posts.xml"
JSON_FEED_FILE = SITE_DIR / "posts.json"

# Filter files
EXTRACT_CITO_FILTER = FILTERS_DIR / "extract-cito.lua"
INSERT_CITO_FILTER = FILTERS_DIR / "insert-cito-in-ref.lua"


# ============================================================================
# GLOB PATTERNS
# ============================================================================

QMD_PATTERNS = {
    "articles": "articles/**/*.qmd",
    "talks": "talks/*.qmd",
    "teaching": "teaching/*.qmd",
    "posts": "posts/*.qmd",
}


# ============================================================================
# HTML/XML IDENTIFIERS
# ============================================================================

# HTML element IDs and classes
REFS_CONTAINER_ID = "refs"
CSL_ENTRY_CLASS = "csl-entry"
CITO_SPAN_CLASS = "cito"
REF_ID_PREFIX = "ref-"

# RDFa and semantic web
DEFAULT_RDFA_PREFIX = (
    "schema: http://schema.org/ "
    "foaf: http://xmlns.com/foaf/0.1/ "
    "dcterms: http://purl.org/dc/terms/ "
    "cito: http://purl.org/spar/cito/"
)
DEFAULT_VOCAB = "http://schema.org/"


# ============================================================================
# EXTERNAL RESOURCES
# ============================================================================

# ROR (Research Organization Registry)
ROR_ICON_URL = (
    "https://raw.githubusercontent.com/ror-community/ror-logos/"
    "refs/heads/main/ror-icon-rgb-transparent.svg"
)

# DOI
DOI_URL_PREFIX = "https://doi.org/"


# ============================================================================
# LINK PATTERNS
# ============================================================================

# Link type detection patterns and their semantic mappings
LINK_PATTERNS = {
    "orcid.org": {
        "rel": "schema:sameAs",
        "property": "schema:identifier",
        "typeof": "schema:PropertyValue",
    },
    "github.com": {
        "rel": "schema:sameAs",
        "property": "schema:codeRepository",
    },
    "linkedin.com": {
        "rel": "schema:sameAs foaf:page",
        "typeof": "schema:ProfilePage",
    },
    "doi.org": {
        "property": "schema:citation",
        "typeof": "schema:ScholarlyArticle",
    },
}


# ============================================================================
# PROCESSING DIRECTORIES
# ============================================================================

# HTML subdirectories to process for semantic annotations
HTML_SUBDIRS = ["articles", "posts", "talks", "teaching", "varia"]


# ============================================================================
# LOGGING
# ============================================================================

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = "INFO"  # Can be: DEBUG, INFO, WARNING, ERROR, CRITICAL


# ============================================================================
# PANDOC
# ============================================================================

PANDOC_FILTERS = [
    EXTRACT_CITO_FILTER,
    INSERT_CITO_FILTER,
]

PANDOC_PDF_ARGS = [
    "--to=pdf",
    "--citeproc",
]
