/**
 * Render *only* the PDFs the site actually wants, via Quarto.
 *
 * Quarto renders LaTeX-quality PDFs with the CiTO citation filters already
 * applied; this script scopes that work to just the documents that declare one,
 * so a `quarto render` does not need to walk every .qmd in the project. A
 * document opts in by carrying `format-links: [pdf]` (posts) or a `pdf` format
 * block (the CV).
 *
 * Mirrors `migrate_posts.py`'s `pdf_requested()`, so the set of PDFs and the
 * set of `pdf:` links in the Eleventy HTML never disagree.
 *
 * Run: node scripts/site/render-pdfs.mjs            (render the PDFs)
 *      node scripts/site/render-pdfs.mjs --dry-run  (list what would render)
 *
 * Quarto is optional for HTML-only dev: a missing binary is a non-fatal skip.
 */
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { dirname, join, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { load as loadYaml } from 'js-yaml';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const POSTS_DIR = join(ROOT, 'posts');

function splitFrontmatter(text) {
  if (!text.startsWith('---')) return { data: {}, body: text };
  const end = text.indexOf('\n---', 3);
  if (end < 0) return { data: {}, body: text };
  return { data: loadYaml(text.slice(4, end)) ?? {}, body: text.slice(end + 4) };
}

/** A post opts in to a PDF via `format-links: [pdf]` (or `- pdf`). */
function pdfRequested(data) {
  const links = data['format-links'];
  if (!links) return false;
  const list = Array.isArray(links) ? links : [links];
  return list.some((item) => String(item).toLowerCase() === 'pdf');
}

/** Collect the .qmd sources that should produce a PDF. */
function collectSources() {
  const sources = [];

  // The CV is a single file, not a posts/* glob.
  const cv = join(ROOT, 'cv.qmd');
  if (existsSync(cv)) sources.push(cv);

  if (existsSync(POSTS_DIR)) {
    for (const file of readdirSync(POSTS_DIR).filter((f) => f.endsWith('.qmd')).sort()) {
      const path = join(POSTS_DIR, file);
      const { data } = splitFrontmatter(readFileSync(path, 'utf-8'));
      if (pdfRequested(data)) sources.push(path);
    }
  }

  return sources;
}

const dryRun = process.argv.includes('--dry-run');
const sources = collectSources();

if (!sources.length) {
  console.log('  no PDFs requested');
  process.exit(0);
}

console.log(`  renders PDF for ${sources.length} document(s):`);
for (const src of sources) console.log(`    - ${src.replace(ROOT + sep, '')}`);

if (dryRun) process.exit(0);

// Probe whether the quarto binary resolves on PATH. Mirrors the CI guard
// (`command -v quarto`); avoids a hard dependency on the `which` npm package.
const probe = spawnSync('quarto', ['--version'], { encoding: 'utf-8', stdio: 'ignore' });
const quartoOnPath = probe.status === 0;

if (!quartoOnPath) {
  const msg = 'quarto is not installed (no quarto on PATH). Install it to render PDFs; skipping.';
  if (process.env.CI) {
    console.error(`  ! ${msg}`);
  } else {
    console.log(`  ! ${msg}`);
  }
  process.exit(0);
}

// Render every opted-in document in one Quarto invocation so the shared
// Lua filters (filters/*.lua) and the _quarto.yml defaults load once.
//
// Quarto still fires the project's `pre-render`/`post-render` hooks (which
// only do HTML-side work: CiTO/ROR/ORCID injection, RSS, a11y, website-spec
// hardening, and a *second* Pandoc-based PDF pass) once per input file.
// That HTML pipeline is the Eleventy site's job now, so signal it away with
// the PDF_ONLY sentinel — the hooks short-circuit to a one-line no-op,
// leaving this path to Quarto's LaTeX renderer alone.
const result = spawnSync('uv', ['run', 'quarto', 'render', ...sources, '--to', 'pdf'], {
  encoding: 'utf-8',
  stdio: ['ignore', 'inherit', 'inherit'],
  env: { ...process.env, PDF_ONLY: '1' },
});

if (result.status !== 0) {
  console.error(`  ! uv run quarto render --to pdf failed (${result.status})`);
  process.exitCode = 1;
} else {
  console.log(`  + rendered ${sources.length} PDF(s) into _site/`);
}
