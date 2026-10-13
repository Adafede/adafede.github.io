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
- **PDFs** --- `scripts/site/render-pdfs.mjs` runs `quarto render --to pdf` for
  exactly the documents that opt in (`cv.qmd` and posts with
  `format-links: [pdf]`). Quarto is optional for local HTML development: if it
  isn't installed the build proceeds without PDFs.

## Build the whole website

One command builds everything --- PDFs, content, and the Eleventy site --- and
is the same command used locally and in CI/deploy:

```sh
npm run build:all
```

That runs, in order:

  | Step   | Script                   | Produces                                                                                                                               |
  | ------ | --------                 | ----------                                                                                                                             |
  | 1      | `npm run render-pdfs`    | `_site/*.pdf` (Quarto + LuaTeX; skipped if no tool chain)                                                                              |
  | 2      | `npm run sync:content`   | `src/content/**`, then `public/` (migrate `.qmd` → Markdown, stage PDFs, optimise images, talk map, expertise, redirects, minify CSS)  |
  | 3      | `npm run build:eleventy` | `_eleventy_site/` (Eleventy + CSS)                                                                                                     |

The PDF step runs **before** the content migration on purpose: the migrator only
writes a `pdf:` link into a post's frontmatter when the PDF already exists in
`_site/posts/`, so reversing the order would drop every PDF button.

### Other commands

  | Command                | Purpose                                                        |
  | ---------              | ---------                                                      |
  | `npm run dev`          | Serve Eleventy locally with hot reload.                        |
  | `npm run build`        | Build only the Eleventy HTML site (no PDFs, no migration).     |
  | `npm run sync:content` | Re-migrate `src/content/` and stage `public/` only.            |
  | `npm run render-pdfs`  | (Re)render only the Quarto PDFs.                               |
  | `npm run check`        | Validate links, RDFa, document structure, and color contrast.  |
  | `npm run check:a11y`   | Run pa11y (axe + HTMLCS) over the served site.                 |

### Deploy

`publish.yml` runs `npm run build:all` and publishes `_eleventy_site/` to GitHub
Pages. PDFs render there because the deploy job installs TeX Live and Quarto.

## CiTO annotations

`filters/*.lua` inject CiTO citation relations into the Quarto PDFs. The
Eleventy HTML side re-asserts the same relations as RDFa (`cito:usesMethodIn`,
`cito:citesAsRecommendedReading`, etc.), so the published HTML and the PDFs
carry consistent citation metadata.
