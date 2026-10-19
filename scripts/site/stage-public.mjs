/**
 * Stages Eleventy's passthrough directory.
 *
 * public/ is what the Eleventy build copies verbatim, but almost none of it is
 * original: images, the well-known directory and the text files all already
 * live at the repository root, and PDFs come from the Quarto build. Committing
 * a second copy would mean two sources of truth for the same avatar and two
 * places to forget an edit, so public/ is generated here and gitignored.
 *
 * PDFs come from the Quarto build (_site/). Quarto renders the PDFs (with
 * CiTO citations and LaTeX-quality typography), so this copies them out of
 * _site/ into public/. A missing PDF is not fatal: a branch that has never run
 * Quarto has no PDFs yet, and the templates check before linking.
 *
 * _headers is not copied here: scripts/site/sri.mjs writes public/_headers so the
 * CSP carries a script hash derived from the script itself.
 *
 * Run: node scripts/site/stage-public.mjs
 */
import {
  copyFileSync,
  cpSync,
  existsSync,
  mkdirSync,
  readdirSync,
} from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PUBLIC = join(ROOT, "public");

/** Directories copied wholesale from the repository root. */
const DIR_SOURCES = ["images", ".well-known"];

/** Individual files copied from the repository root. */
const FILE_SOURCES = [
  "humans.txt",
  "llm.txt",
  "llms.txt",
  "llms-full.txt",
  "robots.txt",
  "site.webmanifest",
];

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

for (const dir of DIR_SOURCES) {
  const from = join(ROOT, dir);
  if (!existsSync(from)) {
    console.log(`  ! missing source directory ${dir}`);
    continue;
  }
  cpSync(from, join(PUBLIC, dir), { recursive: true });
}

for (const file of FILE_SOURCES) {
  const from = join(ROOT, file);
  if (!existsSync(from)) {
    console.log(`  ! missing source file ${file}`);
    continue;
  }
  copyFileSync(from, join(PUBLIC, file));
}

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
