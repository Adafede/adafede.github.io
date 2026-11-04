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

import {
  existsSync,
  readFileSync,
  writeFileSync,
  readdirSync,
  unlinkSync,
} from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { transform } from "lightningcss";

import { htmlFiles } from "./html.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const SITE = join(ROOT, "_eleventy_site");
const CSS_FILE = join(SITE, "styles.css");
const CSS_LINK = /[ \t]*<link rel="stylesheet" href="\/styles\.css"\s*\/?>\n?/g;
const BODY_STYLE = /<style>([\s\S]*?)<\/style>/g;
const CLASS_ATTR = /class="([^"]*)"/g;
const ID_ATTR = /\bid="([^"]*)"/g;
const TAG_NAME = /<([a-z0-9-]+)\b/gi;
const ATTR_NAME = /\s([a-zA-Z_:][\w:.-]*)(?:="([^"]*)")?/g;
const CLASS_IN_SELECTOR = /\.([a-zA-Z_][\w-]*)/g;
const ID_IN_SELECTOR = /#([a-zA-Z_][\w-]*)/g;

if (!existsSync(SITE) || !readdirSync(SITE, { withFileTypes: true }).length) {
  console.error("  ! _eleventy_site is empty; run the Eleventy build first");
  process.exit(1);
}

// The minified sheet is a passthrough copy of build/eleventy/styles.css. If it
// is missing, `bun run minify:css` did not run — say that rather than letting
// readFileSync raise an ENOENT with a bare stack trace.
if (!existsSync(CSS_FILE)) {
  console.error(
    "  ! _eleventy_site/styles.css is missing; run `bun run minify:css`",
  );
  process.exit(1);
}

const css = readFileSync(CSS_FILE, "utf-8").trim();
// Strip url(...) before harvesting so `.svg` in `url("/logos/doi.svg")` is not
// mistaken for a class name.
const selectorsOnly = css.replace(/url\([^)]*\)/g, "");
const definedClasses = [
  ...new Set([...selectorsOnly.matchAll(CLASS_IN_SELECTOR)].map((m) => m[1])),
];
const definedIds = [
  ...new Set(
    [
      ...selectorsOnly
        .replace(/#[0-9a-fA-F]{3,8}\b/g, "")
        .matchAll(ID_IN_SELECTOR),
    ].map((m) => m[1]),
  ),
];

const classesIn = (html) =>
  new Set([...html.matchAll(CLASS_ATTR)].flatMap((m) => m[1].split(/\s+/)));
const idsIn = (html) => new Set([...html.matchAll(ID_ATTR)].map((m) => m[1]));
const tagsIn = (html) =>
  new Set([...html.matchAll(TAG_NAME)].map((m) => m[1].toLowerCase()));
const attrsIn = (html) => {
  const names = new Set();
  const pairs = new Set();
  for (const m of html.matchAll(ATTR_NAME)) {
    const k = m[1].toLowerCase();
    names.add(k);
    if (m[2] !== undefined) pairs.add(`${k}=${m[2]}`);
  }
  return { names, pairs };
};

const pages = htmlFiles(SITE);
const cssBuffer = Buffer.from(css);
const purgedCache = new Map();

let rewritten = 0;
let shipped = 0;

for (const page of pages) {
  const rawHtml = readFileSync(page, "utf-8");

  if (!rawHtml.includes('href="/styles.css"')) continue;

  const extraStyles = [];
  const html = rawHtml.replace(BODY_STYLE, (_, block) => {
    extraStyles.push(block.trim());
    return "";
  });

  const usedClasses = classesIn(html);
  const usedIds = idsIn(html);
  const usedTags = tagsIn(html);
  const usedAttrs = attrsIn(html);
  const key = [
    [...usedClasses].sort().join(" "),
    [...usedIds].sort().join(" "),
    [...usedTags].sort().join(" "),
    [...usedAttrs.names].sort().join(" "),
    [...usedAttrs.pairs].sort().join(" "),
  ].join("|");
  let out = purgedCache.get(key);
  if (out === undefined) {
    const unused = [
      ...definedClasses.filter((name) => !usedClasses.has(name)),
      ...definedIds.filter((name) => !usedIds.has(name)),
    ];
    const { code } = transform({
      filename: "inline.css",
      code: cssBuffer,
      minify: true,
      unusedSymbols: unused,
      visitor: {
        Rule: {
          style(rule) {
            const everyMissing = rule.value.selectors.every((sel) =>
              sel.some((comp) => {
                if (comp.type === "type") {
                  return !usedTags.has(comp.name.toLowerCase());
                }
                if (comp.type === "attribute") {
                  const attr = comp.name.toLowerCase();
                  if (!usedAttrs.names.has(attr)) return true;
                  if (comp.operation?.operator === "equal") {
                    return !usedAttrs.pairs.has(
                      `${attr}=${comp.operation.value}`,
                    );
                  }
                }
                return false;
              }),
            );
            if (everyMissing) return [];
          },
        },
      },
    });
    const rawOut = code.toString();

    // Safety net: purging must never remove a custom property a surviving rule
    // still reads. Referenced-without-fallback-and-nowhere-defined is a build
    // failure, not a silent visual regression.
    const definedVars = new Set(
      [...rawOut.matchAll(/(--[\w-]+)\s*:/g)].map((m) => m[1]),
    );
    const usedVars = new Set(
      [...rawOut.matchAll(/var\(\s*(--[\w-]+)/g)].map((m) => m[1]),
    );
    const orphanVars = [
      ...new Set(
        [...rawOut.matchAll(/var\(\s*(--[\w-]+)\s*([,)])/g)]
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
    out = rawOut
      .replace(/(--[\w-]+)\s*:[^;}]+;?/g, (decl, name) =>
        usedVars.has(name) ? decl : "",
      )
      .replace(/@media[^{]+\{\}/g, "");
    purgedCache.set(key, out);
  }

  const combinedCss = extraStyles.length
    ? `${out}${extraStyles.join("")}`
    : out;
  const styleTag = `<style>${combinedCss}</style>`;
  const updated = html.replace(CSS_LINK, `    ${styleTag}\n`);
  if (updated === rawHtml) continue;

  writeFileSync(page, updated);
  shipped += combinedCss.length;
  rewritten++;
}

unlinkSync(CSS_FILE);

const kb = (n) => `${(n / 1024).toFixed(1)} KB`;
console.log(
  `  inlined ${kb(shipped / rewritten)} per page into ${rewritten} page(s)` +
    ` (from ${kb(css.length)}; ${kb(css.length * rewritten - shipped)} not shipped)`,
);
