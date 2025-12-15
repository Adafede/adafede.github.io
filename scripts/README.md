## Overview

This directory contains scripts for post-processing Quarto output to add:
- **RDFa annotations** for semantic web compatibility
- **CiTO citations** for citation typing ontology
- **ROR affiliations** for research organization registry
- **DOI metadata** for digital object identifiers
- **Schema.org markup** for structured data

## Architecture

```
scripts/
├── config.py                               # Centralized configuration
├── prerender.py                            # Pre-render orchestration
├── postrender.py                           # Post-render orchestration
│
├── Core Processing
│   ├── parse_citos_from_qmd.py             # Extract CiTO from QMD
│   ├── merge_citos.py                      # Merge citation properties
│   ├── process_qmd_directory.py            # Batch QMD processing
│   └── run_pandoc_for_all_qmds.py          # PDF generation
│
├── HTML Injection
│   ├── inject_cito_annotations_in_html.py  # CiTO → HTML
│   ├── inject_ror_in_html.py               # ROR → HTML
│   ├── inject_author_links.py              # Author ORCID/Scholia → HTML
│   └── clean_content_extraction.py         # Semantic markup (WIP)
│
├── RSS/Feed Processing
│   ├── inject_cito_annotations_in_rss.py   # CiTO → RSS
│   ├── inject_doi_in_rss.py                # DOI → RSS
│   └── convert_rss_to_json_feed.py         # RSS → JSON Feed
│
└── Utilities
    └── snake_to_camel_case.py              # String conversion
```

## Usage

### Automatic (via Quarto)

The scripts run automatically during Quarto's build process:

```yaml
# _quarto.yml
project:
  pre-render:
    - scripts/prerender.py
  post-render:
    - scripts/postrender.py
```
