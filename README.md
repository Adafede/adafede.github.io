# adafede.github.io

Personal website of Adriano Rutz. The HTML site is built with
[Eleventy](https://www.11ty.dev/); the PDFs (CV and selected posts) are built
with [Quarto](https://quarto.org/) + LaTeX, so the two stay decoupled: Quarto is
no longer the website renderer, only the PDF renderer.

- **Content source of truth** --- the `.qmd` files and
  `_includes/entities/*.yml`.
- **HTML site** --- [Eleventy](https://www.11ty.dev/) reads Markdown extracted
  from the `.qmd` sources into `src/content/` by
  `scripts/site/migrate_posts.py`.
- **PDFs** --- `scripts/site/render-pdfs.mjs` runs
  `uv run quarto render --to pdf` for exactly the documents that opt in
  (`cv.qmd` and posts with `format-links: [pdf]`). Quarto is optional for local
  HTML development: if it isn't installed the build proceeds without PDFs.

## Install

```sh
# 1. Clone the repository
git clone https://github.com/adafede/adafede.github.io.git
cd adafede.github.io

# 2. Install JavaScript dependencies (requires Bun 1.4+ and Node.js 26+)
bun install --frozen-lockfile

# 3. Install Python dependencies (requires Python 3.14+ and uv)
uv sync
```

## Development

Run the Eleventy development server with hot reload:

```sh
bun run dev
```

Validate the site (links, RDFa, document structure, contrast):

```sh
bun run check
```

Run the test suites (both run in CI):

```sh
bun run test            # both, in order

uv run pytest -q        # Python: the content pipeline and its helpers
node --test tests/      # JavaScript: the Eleventy data loaders and feeds
```

## Build the whole website

One command builds everything --- PDFs, content, and the Eleventy site --- and
is the same command used locally and in CI/deploy:

```sh
bun run build:all
```

That runs, in order:

  | Step | Script                   | Produces                                                                                                                              |
  | ---- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------- |
  | 1    | `bun run render-pdfs`    | `_site/*.pdf` (Quarto + LuaTeX; skipped if no tool chain)                                                                             |
  | 2    | `bun run sync:content`   | `src/content/**`, then `public/` (migrate `.qmd` → Markdown, stage PDFs, optimise images, talk map, expertise, redirects, minify CSS) |
  | 3    | `bun run build:eleventy` | `_eleventy_site/` (Eleventy + CSS)                                                                                                    |

The PDF step runs **before** the content migration on purpose: the migrator only
writes a `pdf:` link into a post's frontmatter when the PDF already exists in
`_site/posts/`, so reversing the order would drop every PDF button.

### Other commands

  | Command                    | Purpose                                                       |
  | ----------------------     | ------------------------------------------------------------- |
  | `bun run dev`              | Serve Eleventy locally with hot reload.                       |
  | `bun run test`             | Run the Python and JavaScript test suites.                    |
  | `bun run build`            | Build only the Eleventy HTML site (no PDFs, no migration).    |
  | `bun run sync:content`     | Re-migrate `src/content/` and stage `public/` only.           |
  | `bun run render-pdfs`      | (Re)render only the Quarto PDFs.                              |
  | `bun run check`            | Validate links, RDFa, document structure, and color contrast. |
  | `bun run check:a11y`       | Run pa11y (axe + HTMLCS) over the served site.                |

`check:a11y` expects a site already being served on port 8080, which is the host
`.pa11yci.json` points at. Run `bun run dev -- --port=8080` alongside it.

### Deploy

Two workflows publish to two different hosts, and which one does what matters
before editing either.

  | Workflow                         | Builds                                  | Publishes to            |
  | -------------------------------- | --------------------------------------- | ----------------------- |
  | `.github/workflows/publish.yml`  | `bun run build:all` → `_eleventy_site/` | GitHub Pages            |
  | `.forgejo/workflows/publish.yml` | `uv run quarto render` → `_site/`       | `adafede.codeberg.page` |

The GitHub one is the site as it stands: Eleventy renders the HTML, and PDFs
render because that job installs TeX Live and Quarto. The Codeberg one still
runs the Quarto pipeline end to end, which is the build Eleventy is replacing.
That workflow is kept working rather than deleted so the two builds can be
compared side by side.

`.github/workflows/site.yml` is the other GitHub workflow: it builds, runs all
four validators, runs both test suites and pa11y, and uploads the result as an
artifact without deploying it.

## CiTO annotations

`filters/*.lua` inject CiTO citation relations into the Quarto PDFs. The
Eleventy HTML side re-asserts the same relations as RDFa (`cito:usesMethodIn`,
`cito:citesAsRecommendedReading`, etc.), so the published HTML and the PDFs
carry consistent citation metadata.

## License

This project is licensed under the GNU Affero General Public License version 3
(AGPL-3.0). See [LICENSE](LICENSE) for the full license text.
