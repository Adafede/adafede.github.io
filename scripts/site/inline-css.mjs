/**
 * Inlines only the CSS each page actually uses, straight into the built HTML.
 *
 * This is the single biggest performance lever on the site: a page ships zero
 * stylesheet requests, so there is no render-blocking fetch at all, and the
 * document omits the rules for markup it does not contain, so the browser never
 * has to parse and match a selector it can never apply. On the home page the
 * 37 KB sheet becomes ~15 KB inline, and the style/layout work Lighthouse
 * attributes to the stylesheet drops with it.
 *
 * How correctness is kept: lightningcss is handed `unusedSymbols`, the class
 * names the sheet defines minus the class names the page's HTML mentions. It
 * drops a selector only when one of its classes is in that set; element,
 * attribute and `:has()`/`:not()`-guarded selectors survive, as do all custom
 * properties. Nothing on the site adds a class at runtime — the one script only
 * toggles `data-*` attributes — so "a class the HTML never mentions" is exactly
 * "a selector that can never match".
 *
 * It runs over the Eleventy output, which has no asset pipeline of its own.
 * The Quarto build needs none of this: Vite already inlines its CSS.
 *
 * Run: node scripts/site/inline-css.mjs   (after an Eleventy build)
 */

import { existsSync, readFileSync, writeFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { transform } from "lightningcss";

import { htmlFiles } from "./html.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const SITE = join(ROOT, "_eleventy_site");
const CSS_FILE = join(SITE, "styles.css");
const CSS_LINK = /[ \t]*<link rel="stylesheet" href="\/styles\.css"\s*\/?>\n?/g;
const CLASS_ATTR = /class="([^"]*)"/g;
const CLASS_IN_SELECTOR = /\.([a-zA-Z_][\w-]*)/g;

if (!existsSync(SITE) || !readdirSync(SITE, { withFileTypes: true }).length) {
  console.error("  ! _eleventy_site is empty; run the Eleventy build first");
  process.exit(1);
}

// The minified sheet is a passthrough copy of build/eleventy/styles.css. If it
// is missing, `npm run minify:css` did not run — say that rather than letting
// readFileSync raise an ENOENT with a bare stack trace.
if (!existsSync(CSS_FILE)) {
  console.error(
    "  ! _eleventy_site/styles.css is missing; run `npm run minify:css`",
  );
  process.exit(1);
}

const css = readFileSync(CSS_FILE, "utf-8").trim();
// Strip url(...) before harvesting so `.svg` in `url("/logos/doi.svg")` is not
// mistaken for a class name.
const selectorsOnly = css.replace(/url\([^)]*\)/g, "");
const defined = [...new Set([...selectorsOnly.matchAll(CLASS_IN_SELECTOR)].map((m) => m[1]))];

const classesIn = (html) =>
  new Set([...html.matchAll(CLASS_ATTR)].flatMap((m) => m[1].split(/\s+/)));

const pages = htmlFiles(SITE);

let rewritten = 0;
let shipped = 0;

for (const page of pages) {
  const html = readFileSync(page, "utf-8");

  if (!html.includes('href="/styles.css"')) continue;

  const used = classesIn(html);
  const unused = defined.filter((name) => !used.has(name));
  const { code } = transform({
    filename: "inline.css",
    code: Buffer.from(css),
    minify: true,
    unusedSymbols: unused,
  });
  const out = code.toString();

  // Safety net: purging must never remove a custom property a surviving rule
  // still reads. Referenced-without-fallback-and-nowhere-defined is a build
  // failure, not a silent visual regression.
  const definedVars = new Set(
    [...out.matchAll(/(--[\w-]+)\s*:/g)].map((m) => m[1]),
  );
  const orphanVars = [
    ...new Set(
      [...out.matchAll(/var\(\s*(--[\w-]+)\s*([,)])/g)]
        .filter(([, name, next]) => next === ")" && !definedVars.has(name))
        .map(([, name]) => name),
    ),
  ];
  if (orphanVars.length) {
    console.error(
      `  ! ${page.replace(`${ROOT}/`, "")}: unresolved custom property${orphanVars.length > 1 ? "ies" : "y"} ${orphanVars.join(", ")}`,
    );
    process.exit(1);
  }

  const styleTag = `<style>${out}</style>`;
  const updated = html.replace(CSS_LINK, `    ${styleTag}\n`);
  if (updated === html) continue;

  writeFileSync(page, updated);
  shipped += out.length;
  rewritten++;
}

const kb = (n) => `${(n / 1024).toFixed(1)} KB`;
console.log(
  `  inlined ${kb(shipped / rewritten)} per page into ${rewritten} page(s)` +
    ` (from ${kb(css.length)}; ${kb(css.length * rewritten - shipped)} not shipped)`,
);
