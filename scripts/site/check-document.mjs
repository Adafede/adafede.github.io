/**
 * Checks the document-level facts every page must get right.
 *
 * Accessibility tooling catches what a rule can express: contrast, labels,
 * names, roles. It does not catch the rest of what makes a page correct, which
 * is why this exists as a separate pass:
 *
 *   - one <h1>, and no skipped heading levels (screen readers navigate by level)
 *   - a <main> landmark, a skip link, a <html lang> (the three things that make
 *     a document navigable at all)
 *   - a canonical URL and a description, on every page and not just some: a
 *     canonical link present on a subset reads as a decision rather than an
 *     omission
 *   - intrinsic width/height on every <img> (an image without them is a layout
 *     shift the browser cannot reserve space for)
 *   - no double-escaped text, which is what a description looks like when it
 *     has been through two escaping passes
 *   - no empty links, and no external link missing rel="noopener"
 *
 * Run: node scripts/site/check-document.mjs _eleventy_site
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const roots = process.argv.slice(2);
if (!roots.length) {
  console.error('usage: check-document.mjs <dir> [dir...]');
  process.exit(2);
}

/** The redirect stubs are deliberately minimal documents. */
const isStub = (html) => html.includes('http-equiv="refresh"');

function htmlFiles(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) out.push(...htmlFiles(path));
    else if (path.endsWith('.html')) out.push(path);
  }
  return out;
}

/** The document, with the stylesheet, the inline <style> and scripts removed. */
function documentOf(html) {
  return html
    .replace(/<style[\s\S]*?<\/style>/g, '')
    .replace(/<script[\s\S]*?<\/script>/g, '');
}

function check(html) {
  const problems = [];
  const doc = documentOf(html);

  const lang = doc.match(/<html\b[^>]*\blang="([^"]*)"/);
  if (!lang || !lang[1].trim()) problems.push('no lang on <html>');

  // Every PDF link has to say it is a PDF. This is what WAVE's "Link to a PDF
  // document" alert is about: the file type is the one thing a reader cannot
  // infer from the URL, and a background icon does not reach a screen reader.
  // Checked against the link's own text rather than a class, so the guarantee
  // holds however the label happens to be marked up.
  for (const m of doc.matchAll(/<a\b([^>]*?)href="[^"]*\.pdf(?:#[^"]*)?"([^>]*)>([\s\S]*?)<\/a>/gi)) {
    const label = m[3].replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
    if (!/\bpdf\b/i.test(label)) {
      problems.push(`PDF link whose text does not say PDF: "${label || '(empty)'}"`);
    }
  }

  if (!/<a class="skip-link"/.test(doc)) problems.push('no skip link');
  if (!/<main\b/.test(doc)) problems.push('no <main> landmark');

  // Headings inside <main> only: a page can legitimately have an <h1> in a
  // hidden template block, and what matters is what the reader can reach.
  const main = doc.slice(doc.indexOf('<main'));

  // The <h1> must not be a copy of the <title>. WAVE reports that as a
  // "possible heading reference": on a page where the two are identical the
  // heading carries no information the reader did not already have from the tab,
  // and the usual way it happens is a landing page titled with the site name.
  const docTitle = doc.match(/<title>([\s\S]*?)<\/title>/);
  const h1 = main.match(/<h1\b[^>]*>([\s\S]*?)<\/h1>/);
  if (docTitle && h1) {
    const norm = (value) =>
      value
        .replace(/<[^>]+>/g, ' ')
        .replace(/\s+—\s*[^\s—]+$/, '')
        .replace(/[\s\u00a0]+/g, ' ')
        .trim()
        .toLowerCase();
    if (norm(h1[1]) === norm(docTitle[1])) {
      problems.push(`<h1> "${norm(h1[1])}" repeats the <title>`);
    }
  }
  const headings = [...main.matchAll(/<h([1-6])[\s>]/g)].map((m) => Number(m[1]));

  const h1s = headings.filter((level) => level === 1).length;
  if (h1s === 0) problems.push('no <h1> in <main>');
  if (h1s > 1) problems.push(`${h1s} <h1> elements in <main> (expected 1)`);

  let previous = 0;
  for (const level of headings) {
    if (previous && level > previous + 1) {
      problems.push(`heading level jumps from h${previous} to h${level}`);
      break;
    }
    previous = level;
  }

  if (!/<link rel="canonical"/.test(doc)) problems.push('no canonical URL');
  if (!/<meta name="description"/.test(doc)) problems.push('no meta description');

  // Escaped twice: the first pass turns `<`, the second turns `&`, so the
  // reader and the crawler see literal `&lt;`.
  const doubleEscaped = doc.match(/&amp;(?:lt|gt|amp|quot|#\d+);/);
  if (doubleEscaped) problems.push(`double-escaped text: ${doubleEscaped[0]}`);

  for (const img of doc.matchAll(/<img\b[^>]*>/g)) {
    const tag = img[0];
    // width/height must both be there, and must describe the same box.
    const w = tag.match(/\bwidth="(\d+)"/);
    const h = tag.match(/\bheight="(\d+)"/);
    if (!w || !h) problems.push(`<img> without intrinsic size: ${tag.slice(0, 80)}`);
    if (tag.includes('alt=') === false) problems.push(`<img> without alt: ${tag.slice(0, 80)}`);
  }

  for (const link of doc.matchAll(/<a\b[^>]*>/g)) {
    const tag = link[0];
    if (/\shref=""/.test(tag)) problems.push('empty href');
    if (/\starget="_blank"/.test(tag) && !/\srel="[^"]*noopener/.test(tag)) {
      problems.push('target="_blank" without rel="noopener"');
    }
  }

  // An iframe is an interactive control with no keyboard focus of its own; it
  // needs a name, and it should not be able to reach back into this page.
  for (const frame of doc.matchAll(/<iframe\b[^>]*>/g)) {
    const tag = frame[0];
    if (!/\stitle="[^"]+"/.test(tag)) problems.push('<iframe> without title');
    if (!/\ssandbox=/.test(tag)) problems.push('<iframe> without sandbox');
  }

  return problems;
}

let total = 0;

for (const root of roots) {
  let pages = 0;
  const failures = [];

  for (const page of htmlFiles(root)) {
    const html = readFileSync(page, 'utf-8');
    if (isStub(html)) continue;
    pages++;
    const problems = check(html);
    if (problems.length) {
      failures.push([page.slice(root.length) || '/', [...new Set(problems)]]);
    }
  }

  total += failures.reduce((sum, [, problems]) => sum + problems.length, 0);
  console.log(`${root}: ${pages} pages, ${failures.length} with problems`);
  for (const [name, problems] of failures.slice(0, 12)) {
    console.log(`  ${name}`);
    for (const problem of problems) console.log(`    - ${problem}`);
  }
  if (failures.length > 12) console.log(`  ... and ${failures.length - 12} more`);
}

process.exit(total ? 1 : 0);
