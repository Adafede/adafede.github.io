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
import { readFileSync } from "node:fs";

import { htmlFiles, removeScriptAndStyle } from "./html.mjs";

const roots = process.argv.slice(2);
if (!roots.length) {
  console.error("usage: check-rdfa.mjs <dir> [dir...]");
  process.exit(2);
}

/** Attributes whose value may contain prefixed terms. */
const RDFA_ATTRS = [
  "about",
  "resource",
  "property",
  "rel",
  "typeof",
  "datatype",
  "vocab",
];

/**
 * The default RDFa terms, which are used unprefixed and need no declaration.
 * Deliberately short: anything not here has to be declared.
 */
const BARE_TERMS = new Set([
  "a",
  "describedby",
  "label",
  "title",
  "type",
  "value",
  "xml:lang",
  "role",
]);

/** Absolute IRIs and non-CURIE URI schemes whose first colon is a scheme separator. */
const IRI = /^(?:[a-z][a-z0-9+.-]*:\/\/|(?:mailto|tel|urn|data|javascript|about):)/i;

/** Expected local-part syntax for registry prefixes whose IDs have a fixed grammar. */
const LOCAL_PATTERNS = {
  wd: /^[QPML]\d+$/,
  wdt: /^P\d+$/,
  wdtn: /^P\d+$/,
  wdno: /^P\d+$/,
  p: /^P\d+$/,
  ps: /^P\d+$/,
  pq: /^P\d+$/,
  orcid: /^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$/,
  ror: /^0[a-z0-9]{6}\d{2}$/,
};

let totalProblems = 0;

for (const rawRoot of roots) {
  const root = rawRoot.replace(/\/+$/, "");
  const pages = htmlFiles(root);
  const problems = [];

  for (const page of pages) {
    const rawHtml = readFileSync(page, "utf-8");
    const html = removeScriptAndStyle(rawHtml).replace(/<!--[\s\S]*?-->/g, "");
    const name = page.slice(root.length) || "/";

    // Prefixes declared anywhere on the page (including <html prefix="...">).
    const declared = new Set();
    for (const m of html.matchAll(/prefix="([^"]*)"/g)) {
      for (const pair of m[1].matchAll(/([\w-]+):\s*(\S+)/g)) {
        declared.add(pair[1]);
      }
    }

    // Strip <head> before scanning elements so Open Graph / Twitter <meta> tags
    // are not mistaken for body RDFa, while body <meta property="..."> tags ARE
    // validated.
    const bodyScope = html.replace(/<head\b[^>]*>[\s\S]*?<\/head>/gi, "");

    for (const m of bodyScope.matchAll(/<[^>]+>/g)) {
      const tag = m[0];
      if (tag.startsWith("<link")) continue;
      for (const attr of RDFA_ATTRS) {
        const value = tag.match(new RegExp(`\\b${attr}="([^"]*)"`))?.[1];
        if (!value) continue;
        for (const term of value.split(/\s+/)) {
          if (!term || BARE_TERMS.has(term)) continue;
          if (!term.includes(":")) continue;
          if (IRI.test(term)) continue;
          const colon = term.indexOf(":");
          const prefix = term.slice(0, colon);
          const local = term.slice(colon + 1);
          if (!declared.has(prefix)) {
            problems.push(
              `${name}: <${tag.slice(0, 90)}…> uses undeclared prefix "${prefix}:"`,
            );
            break;
          }
          const pattern = LOCAL_PATTERNS[prefix];
          if (pattern && !pattern.test(local)) {
            problems.push(
              `${name}: <${tag.slice(0, 90)}…> has malformed CURIE "${term}"`,
            );
            break;
          }
        }
      }
    }
  }

  const uniqueProblems = [...new Set(problems)];
  totalProblems += uniqueProblems.length;
  console.log(
    `${rawRoot}: ${pages.length} pages, ${uniqueProblems.length} RDFa problem(s)`,
  );
  for (const problem of uniqueProblems.slice(0, 20))
    console.log(`  ${problem}`);
}

process.exit(totalProblems ? 1 : 0);
