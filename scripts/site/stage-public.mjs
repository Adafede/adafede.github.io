/**
 * Stages generated files for Eleventy's passthrough directory.
 *
 * public/ is gitignored and holds build-derived artifacts that are not already
 * present at stable repository paths. PDFs come from the Quarto build (_site/):
 * this copies them out of _site/ into public/. A missing PDF is not fatal: a
 * branch that has never run Quarto has no PDFs yet, and the templates check
 * before linking.
 *
 * Source-of-truth files that already live at the repository root (images,
 * .well-known, robots/llm/manifest text files, _headers) are copied directly by
 * Eleventy and must not be duplicated here, otherwise passthrough copy would try
 * to write the same output from two inputs.
 *
 * Run: node scripts/site/stage-public.mjs
 */
import { copyFileSync, existsSync, mkdirSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PUBLIC = join(ROOT, "public");

/**
 * Quarto build output that the site links to.
 *
 * The destinations are the Quarto ones. PDFs used to be re-homed under /pdf/,
 * which put the two builds at different URLs for the same file; a permalink that
 * moves is a broken link in the wild, so nothing gets re-homed.
 */
const PDF_SOURCES = [
  { from: "_site/posts", to: "posts" },
  { from: "_site", to: ".", files: ["cv.pdf", "cv-academic.pdf"] },
];

mkdirSync(PUBLIC, { recursive: true });

// PDFs. Missing ones are not fatal: a branch that has never run Quarto simply
// has no PDFs yet, and the templates already check before linking.
let pdfCount = 0;
for (const spec of PDF_SOURCES) {
  const dir = join(ROOT, spec.from);
  if (!existsSync(dir)) continue;
  const target = join(PUBLIC, spec.to);
  mkdirSync(target, { recursive: true });

  if (spec.files) {
    for (const file of spec.files) {
      const src = join(dir, file);
      if (existsSync(src)) {
        copyFileSync(src, join(target, file));
        pdfCount++;
      }
    }
    continue;
  }

  for (const file of readdirSync(dir)) {
    if (!file.endsWith(".pdf")) continue;
    copyFileSync(join(dir, file), join(target, file));
    pdfCount++;
  }
}

console.log(`  + public/ staged (${pdfCount} PDF${pdfCount === 1 ? "" : "s"})`);
