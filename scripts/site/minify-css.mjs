/**
 * Minifies the shared stylesheet into build/eleventy/styles.css.
 *
 * Eleventy has no asset pipeline, so a static site ships the file verbatim —
 * which Lighthouse counts as an unminified-CSS opportunity. Running this after
 * any change to src/styles/global.css keeps the build clean.
 *
 * src/styles/global.css stays the single source of truth; this is build output
 * and is not written into the passthrough directory at all, because
 * scripts/site/inline-css.mjs folds it into every page.
 *
 * Run: node scripts/site/minify-css.mjs
 */
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { transform } from 'lightningcss';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const SOURCE = join(ROOT, 'src', 'styles', 'global.css');
const TARGET = join(ROOT, 'build', 'eleventy', 'styles.css');

const source = readFileSync(SOURCE);
const { code } = transform({ filename: SOURCE, code: source, minify: true });

mkdirSync(dirname(TARGET), { recursive: true });
writeFileSync(TARGET, code);

const kb = (n) => `${(n / 1024).toFixed(0)} KB`;
console.log(`  + build/eleventy/styles.css (${kb(source.length)} -> ${kb(code.length)})`);
