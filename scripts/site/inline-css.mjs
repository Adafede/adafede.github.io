/**
 * Inlines the stylesheet into the built HTML.
 *
 * This is the single biggest performance lever on the site, and the approach
 * speedlify.dev uses: it ships zero stylesheets, so there is no render-blocking
 * request at all. The document carries its styles in the first response.
 *
 * It runs over the Eleventy output, which has no asset pipeline, so
 * and inlines CSS through Vite already, so this does not apply there.
 *
 * The minified sheet is inlined once per page: ~15 KB gzipped to ~4 KB, served
 * from cache on repeat visits, and never blocks first paint.
 *
 * Run: node scripts/site/inline-css.mjs   (after an Eleventy build)
 */

import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const SITE = join(ROOT, '_eleventy_site');
const CSS_FILE = join(SITE, 'styles.css');
const CSS_LINK = /[ \t]*<link rel="stylesheet" href="\/styles\.css"\s*\/?>\n?/g;

function htmlFiles(dir) {
  const out = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...htmlFiles(path));
    else if (entry.name.endsWith('.html')) out.push(path);
  }
  return out;
}

if (!readdirSync(SITE, { withFileTypes: true }).length) {
  console.error('  ! _eleventy_site is empty; run the Eleventy build first');
  process.exit(1);
}

const css = readFileSync(CSS_FILE, 'utf-8').trim();
const styleTag = `<style>${css}</style>`;
const pages = htmlFiles(SITE);

let rewritten = 0;

for (const page of pages) {
  const html = readFileSync(page, 'utf-8');

  if (!html.includes('href="/styles.css"')) continue;

  const updated = html.replace(CSS_LINK, `    ${styleTag}\n`);
  if (updated === html) continue;

  writeFileSync(page, updated);
  rewritten++;
}

console.log(`  inlined ${css.length} bytes of CSS into ${rewritten} page(s)`);
