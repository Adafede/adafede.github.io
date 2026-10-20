/**
 * Reduce a Quarto `_site/` to the PDFs the build actually consumes.
 *
 * Quarto is configured as a *website* project (`_quarto.yml`), so rendering even
 * a single `.qmd --to pdf` also copies the whole project tree into `_site/`: the
 * generated `src/content/`, `public/`, a nested `_eleventy_site/`, the vendored
 * `site_libs/`, `search.json`, and a full stale HTML site. None of it is used —
 * `stage-public.mjs` reads only the CV PDFs and `_site/posts/*.pdf` — but it is
 * ~9 MB of churn that makes `_site/` look like a second, confusing website.
 *
 * `render-pdfs.mjs` calls this after a successful render so the PDFs are all
 * that remain. Extracted here so it can be unit-tested without invoking Quarto.
 */

import { readdirSync, rmSync } from "node:fs";
import { join } from "node:path";

/** The PDFs kept at the root of `_site/`. */
export const ROOT_PDFS = ["cv.pdf", "cv-academic.pdf"];

/**
 * Deletes everything in `dir` except the PDFs the pipeline reads.
 *
 * Files are removed; the (now empty) directory tree is left so the next Quarto
 * render does not have to recreate it. A missing directory is a no-op: a branch
 * that has never run Quarto has no `_site/` yet.
 *
 * @param {string} dir absolute path to the `_site/` directory
 * @returns {number} count of top-level entries removed
 */
export function pruneSiteToPdfs(dir) {
  let entries;
  try {
    entries = readdirSync(dir);
  } catch {
    return 0;
  }

  const keep = new Set(ROOT_PDFS);
  let removed = 0;
  for (const entry of entries) {
    if (keep.has(entry)) continue;
    if (entry === "posts") {
      // Keep only the post PDFs; drop the rendered HTML and assets beside them.
      const postsDir = join(dir, "posts");
      for (const post of readdirSync(postsDir)) {
        if (post.endsWith(".pdf")) continue;
        rmSync(join(postsDir, post), { recursive: true, force: true });
        removed++;
      }
      continue;
    }
    rmSync(join(dir, entry), { recursive: true, force: true });
    removed++;
  }
  return removed;
}
