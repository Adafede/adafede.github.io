/**
 * Checks that the RDFa in a built site is internally consistent.
 *
 * The site is full of RDFa: `vocab`, `typeof`, `about`, `resource`, and the
 * Wikidata prefixes that turn a mention of a person into a link to their item.
 * That markup is invisible in a screenshot and easy to break silently — rename
 * a prefix, drop the `prefix` attribute, and every `about="wd:Q123"` on the
 * page silently stops resolving while the page still looks perfect.
 *
 * So this asserts the property that actually matters: every prefixed term used
 * on a page is declared in that page's prefix list. A full RDFa parse would be
 * more thorough, but this catches the failures that happen in practice and runs
 * with no dependencies.
 *
 * Run: node scripts/site/check-rdfa.mjs _eleventy_site
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const roots = process.argv.slice(2);
if (!roots.length) {
  console.error('usage: check-rdfa.mjs <dir> [dir...]');
  process.exit(2);
}

/** Attributes whose value may contain prefixed terms. */
const RDFA_ATTRS = ['about', 'resource', 'property', 'rel', 'typeof', 'datatype', 'vocab'];

/**
 * The default RDFa terms, which are used unprefixed and need no declaration.
 * Deliberately short: anything not here has to be declared.
 */
const BARE_TERMS = new Set([
  'a', 'describedby', 'label', 'title', 'type', 'value', 'xml:lang', 'role',
]);

/** An absolute IRI: scheme://... — its first colon is a scheme separator. */
const IRI = /^[a-z][a-z0-9+.-]*:\/\//i;

function htmlFiles(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) out.push(...htmlFiles(path));
    else if (path.endsWith('.html')) out.push(path);
  }
  return out;
}

let totalProblems = 0;

for (const root of roots) {
  const pages = htmlFiles(root);
  const problems = [];

  for (const page of pages) {
    const html = readFileSync(page, 'utf-8');
    const name = page.slice(root.length) || '/';

    // Prefixes declared anywhere on the page. The site declares them once on a
    // hidden element, as Quarto does, so this collects all of them.
    const declared = new Set();
    for (const m of html.matchAll(/prefix="([^"]*)"/g)) {
      // Each entry is `prefix: iri` with a space after the colon, which is the
      // RDFa serialization. Matching `name: iri` directly keeps the IRI's own
      // colons out of the prefix, so `wd: http://…` yields `wd`, not `wd` and
      // a bogus `http`.
      for (const pair of m[1].matchAll(/([\w-]+):\s*(\S+)/g)) {
        declared.add(pair[1]);
      }
    }

    // A page with no prefixes declared is fine as long as it uses none; the
    // per-term check below catches that case on its own.
    for (const m of html.matchAll(/<[^>]+>/g)) {
      const tag = m[0];
      // <meta> and <link> carry Open Graph and schema.org values, which reuse
      // the same attribute names but are not RDFa and declare no prefixes. The
      // RDFa that matters is in the body.
      if (tag.startsWith('<meta') || tag.startsWith('<link')) continue;
      for (const attr of RDFA_ATTRS) {
        const value = tag.match(new RegExp(`\\b${attr}="([^"]*)"`))?.[1];
        if (!value) continue;
        for (const term of value.split(/\s+/)) {
          if (!term || BARE_TERMS.has(term)) continue;
          // An absolute IRI is not a prefixed term: `https:` is its scheme, not
          // a declared prefix. Skipping only on a missing colon reported these
          // as undeclared prefixes.
          if (!term.includes(':')) continue;
          if (IRI.test(term)) continue; // A bare IRI or term.
          const prefix = term.slice(0, term.indexOf(':'));
          if (!declared.has(prefix)) {
            problems.push(`${name}: <${tag.slice(0, 90)}…> uses undeclared prefix "${prefix}:"`);
            break;
          }
        }
      }
    }
  }

  totalProblems += problems.length;
  console.log(`${root}: ${pages.length} pages, ${problems.length} RDFa problem(s)`);
  for (const problem of [...new Set(problems)].slice(0, 20)) console.log(`  ${problem}`);
}

process.exit(totalProblems ? 1 : 0);
