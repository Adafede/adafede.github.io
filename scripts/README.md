# Scripts Directory

Post-processing scripts for Quarto output with semantic web annotations.

## Overview

This directory contains a **clean 4-layer architecture** for processing Quarto output:
- **CiTO citations** - Citation typing ontology annotations
- **ROR affiliations** - Research organization registry links
- **ORCID integration** - Author identification and Scholia links
- **DOI metadata** - Digital object identifiers
- **Semantic markup** - RDFa and Schema.org annotations

## Architecture

```
┌─────────────────────────────────────┐
│      ORCHESTRATION LAYER            │  ← Coordinates workflow
│    prerender.py, postrender.py      │
└─────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────┐
│       UTILITIES LAYER               │  ← Specialized processing
│  RSS • PDF • QMD • TalkMap          │
└─────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────┐
│       SERVICES LAYER                │  ← Business logic
│  Cito • Metadata • Author • ROR     │
└─────────────────────────────────────┘
        ▼                    ▼
┌──────────────┐    ┌──────────────────┐
│   DOMAIN     │    │ INFRASTRUCTURE   │
│   MODELS     │    │   UTILITIES      │
└──────────────┘    └──────────────────┘
```

## Directory Structure

```
scripts/
├── infrastructure/          # Reusable utilities
│   ├── filesystem.py        # File operations
│   ├── html_processor.py    # HTML manipulation
│   ├── logger.py            # Centralized logging
│   └── yaml_loader.py       # YAML parsing
│
├── domain/                  # Business models
│   ├── citation.py          # Citation, CitoProperty
│   ├── content.py           # ContentMetadata, FeedItem
│   └── post.py              # Post, Author, Affiliation
│
├── services/                # Business logic
│   ├── cito_service.py      # CiTO citation handling
│   ├── metadata_service.py  # YAML metadata updates
│   ├── author_service.py    # ORCID & Scholia links
│   └── ror_service.py       # ROR affiliation linking
│
├── utilities/               # Specialized processing
│   ├── convert_rss_to_json_feed.py       # RSS to JSON conversion
│   ├── inject_cito_annotations_in_rss.py # CiTO RSS injection
│   ├── inject_doi_in_rss.py              # DOI RSS injection
│   ├── process_qmd_directory.py          # Batch QMD processing
│   ├── run_pandoc_for_all_qmds.py        # PDF generation
│   └── talkmap.py                        # Talk location mapping
│
├── prerender.py             # Pre-render orchestration
├── postrender.py            # Post-render orchestration
└── config.py                # Configuration
```

## Quick Start

### Build Site
```bash
uv run quarto render
```

### Use in Code
```python
import sys
sys.path.insert(0, 'scripts')

from services import CitoService, AuthorService
from infrastructure import FileSystem, HtmlProcessor
from utilities import talkmap, process_qmd_directory

# Initialize
fs = FileSystem(project_root)
cito = CitoService(fs, HtmlProcessor())

# Use
posts = fs.find_posts("posts")
citations = cito.parse_citations_from_qmd(posts[0])
```

## Automatic Processing

The scripts run automatically during Quarto's build process:

```yaml
# _quarto.yml
project:
  pre-render:
    - scripts/prerender.py
  post-render:
    - scripts/postrender.py
```

### What Happens

**Pre-render (`prerender.py`):**
- Updates post metadata (dates, DOIs)
- Ensures all QMD files have correct frontmatter

**Post-render (`postrender.py`):**
1. Generates PDFs with Pandoc
2. Processes articles, talks, teaching (injects ROR + ORCID)
3. Processes posts (injects CiTO + ROR + ORCID)
4. Updates RSS feeds (DOIs + CiTO annotations)
5. Converts RSS to JSON Feed
