# AGENTS.md

## Stack
Eleventy 3 (JS site) + Quarto/LaTeX (PDFs only) + Python 3.14 build scripts.
Node 26+, `uv`, `quarto` optional for HTML work.

## Setup
```sh
npm ci && uv sync
```

## Verify — start here
```sh
npm test                                    # 92 pytest + 25 node --test, ~5s
npm run build:eleventy && npm run check    # links + rdfa + document + contrast, ~1.5s
npm run lint                                # the full prek hook set, ~17s
```

`npm run check` reads `_eleventy_site/`, so **build first or you validate stale HTML**.
On a clean clone it fails with a bare `ENOENT` stack trace rather than a useful message.

Fast subsets:
```sh
uv run pytest tests/test_url_utils.py -q            # one file
uv run pytest tests/test_url_utils.py -k test_url_has_host -q   # one test
node --test tests/bib.test.mjs                      # one JS file

npm run lint -- check-agent-docs                    # one hook
uv run --with ruff ruff check .                     # one linter
uv run --with ruff ruff format --check .
uv run deptry .
uv run --with typos typos

npm run check:links                                 # the dir is already in package.json
node scripts/site/check-links.mjs _eleventy_site    # …or pass it directly when you want a
node scripts/site/check-rdfa.mjs _eleventy_site    #   different output dir
node scripts/site/check-document.mjs _eleventy_site
node scripts/site/render-pdfs.mjs --dry-run         # list the PDFs that would render
npm run check:agent-docs                            # AGENTS.md still resolves
npm run check:agent-endpoints                       # published agent URLs still resolve
npm run check:graph                                 # how stale the knowledge graph is
```
Only `check-links.mjs`, `check-rdfa.mjs` and `check-document.mjs` take a directory
(`process.argv.slice(2)`). `render-pdfs.mjs` takes `--dry-run`; the other
`scripts/site/*.mjs` take no arguments.

Build:
```sh
npm run build:all        # PDFs -> sync:content -> eleventy (CI + deploy)
npm run clean            # drop _site/, _eleventy_site/, public/, build/
npm run dev              # eleventy --serve
```

`npm run clean` matters because none of the build steps empty their output.
Eleventy's passthrough copy and `inline-css.mjs` overwrite the files they touch
and leave the rest, so a file that stops being generated (an inlined sheet, a
deleted script) lingers. The CI build starts from a clean checkout, so a stale
local output never reaches Pages — but it will mislead `npm run check`, which
reads `_eleventy_site/`.

## Definition of done
1. `npm test` passes.
2. `npm run build:eleventy && npm run check` passes against a **fresh** build.
3. `npm run check:agent-endpoints` passes — it needs the build from step 2.
4. `npm run lint` passes. CI runs it too, so a local skip is a CI failure.
5. If you touched `_includes/entities/` or a `.qmd`, the change flows through
   `npm run sync:content` — never patch `src/content/` directly.
6. If you touched a `.py` or `.mjs` under `scripts/`, run `npm run graph:update`
   (~3s, no model access) or the pre-commit graph hook will fail the commit.
7. Commit messages are Conventional Commits (`feat:`, `fix:`, `chore(scope):`).

## Repo map
- `eleventy.config.mjs` (1277 lines, 31 `addFilter` calls) — all filters, collections,
  markdown-it plugins. The hottest file; read it by line range, never whole.
- `src/eleventy/**` — Nunjucks templates (`pages/`, `_includes/`) and `_data/*.js`.
- `src/eleventy/static/` — passthrough assets, including the logo set.
- `src/lib/*.mjs` — bib (tested), jsonFeed and prefixes (currently untested).
- `src/styles/global.css` (2909 lines) — the whole design system as CSS custom properties.
- `src/content/**` — GENERATED, gitignored. Never edit.
- `scripts/site/*.py` — content pipeline: `migrate_posts`, `build_talkmap`,
  `build_expertise`, `academic_cv` (runs in `cv-academic.qmd`'s python cell),
  `optimize_artwork` (runs from `fetch-artwork.mjs`).
- `scripts/site/*.mjs` — build steps + the four validators.
- `scripts/{services,infrastructure}/*.py` — Quarto pre/post-render processors.
- `scripts/config.py`, `scripts/url_utils.py` — shared config and URL helpers.
- `scripts/utilities/*.py` + `filters/*.lua` + `_extensions/` — legacy Quarto-era code
  (`fix_accessibility.py` and `enforce_website_spec.py` are the live exceptions).
- `_includes/entities/{authors,affiliations}/*.yml` — content source of truth for
  people and affiliations.
- `_cache/*.json` — committed caches (geocode, expertise).
- `.well-known/`, `llm.txt`, `llms.txt`, `llms-full.txt`, `humans.txt` — published
  as site resources (`_quarto.yml`), so their URLs are part of the published API.
- Output: `_eleventy_site/` (HTML), `_site/` (PDFs), `public/` (staging).
  `render-pdfs.mjs` prunes `_site/` back to the four PDFs it renders: Quarto is
  a *website* project, so a `--to pdf` render also copies the whole repo tree
  into `_site/` (~9 MB of `src/`, `public/`, `site_libs/`, stale HTML) that
  nothing reads.

## Conventions that differ from defaults
- Python: full type hints, `from __future__ import annotations`, `logging` not print,
  docstrings on every public function. `ruff` target is pinned to py313 on purpose
  (py313 target is deliberate — do not "fix" it, see `pyproject.toml`).
- Tests: `pytest` with `tests/conftest.py`; behaviour-named test functions.
  Python tests are `test_*.py`, JS tests are `*.test.mjs` (not `test_*.js`).
- The Quarto CSS design system is shared with Eleventy (`_freeze`). Edit both sides
  of a design token or the PDF and HTML drift.
- Every `.qmd` post has a matching record in `_includes/entities/`.
- Two build pipelines exist on purpose — `.github/workflows/publish.yml` runs
  `npm run build:all`, `.forgejo/workflows/publish.yml` still runs the legacy
  `uv run quarto render`. Read `README.md` "Deploy" before editing either.

## Do not touch
- `src/content/`, `_eleventy_site/`, `public/`, `build/` — generated, and ignored
  by git. An edit there is silently overwritten by the next `npm run sync:content`.
- `_cache/*.json` — committed cache; delete deliberately, never hand-edit.
- `cv.tex`, `cv-academic.tex` — Quarto output, also gitignored.
- `.venv/`, `node_modules/`, `.quarto/`, `_freeze/`, `graphify-out/`.

## Navigation
1. `rg` with tight globs first: get filenames and counts, then drill into a line range.
   Never read a whole large file; never read generated output.
2. `graphify query "..."` is useful for the **Python** layer only. It has 0 nodes
   for the Nunjucks templates and the CSS, and 2 for the 222 entity files, so
   for `src/eleventy/**`, `src/styles/**` and `_includes/**` it will point at the
   wrong file. It is worth about 41x fewer tokens per query here — run
   `graphify benchmark` for the current number. Three more verbs worth knowing:
   `graphify path "A" "B"` (shortest path), `graphify explain "Node"` (what a
   node connects to), `graphify benchmark` (token saving). All take a plain
   question; add `--budget N` to `query` when the answer runs long.
3. The graph keeps itself current: `graphify hook install` puts a post-commit
   (and post-checkout/post-merge) hook in `.git/hooks/`, which rebuilds the
   changed files in ~3s with no LLM. That is local and uncommitted. Until it is
   installed, `npm run graph:update` does the same thing by hand, and
   `npm run check:graph` reports how far behind the graph is.
4. Quiet flags, summarize output, report only failures. Target one test, not the
   suite, unless at a pass boundary.
5. Keep every command and path in this file runnable — `npm run check:agent-docs`
   enforces it, and runs in pre-commit and CI.

## Anti-drift gates
Every check below runs without arguments, and is wired into pre-commit or CI:

| Check | Guards |
| ----- | ------ |
| `npm run check:agent-docs` | every command and path named in this file resolves |
| `npm run check:local-paths` | no tracked file contains an absolute home-directory path (`/Users/…`, `C:\Users\…`, `/home/…`) |
| `npm run check:agent-endpoints` | the URLs published under `.well-known/` and `llm*.txt` still exist; `llm.txt` still matches `llms.txt` |
| `npm run check:graph` | the knowledge graph matches the working tree |
| `npm run lint` | ruff, ruff-format, deptry, ty, typos, vale, zizmor, panache |

If one of these fails, fix the file it names — do not weaken the check.
