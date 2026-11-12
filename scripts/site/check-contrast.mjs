/**
 * Verify WCAG contrast for the palette in src/styles/global.css.
 *
 * Colour is declared with CSS `light-dark(light, dark)`, so the two themes come
 * from one declaration and cannot drift apart. This resolves both halves and
 * checks every pair that carries text or UI.
 *
 * Run: bun run check:contrast
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const SHEET = join(ROOT, "src", "styles", "global.css");

/** Pull `--name: value;` out of a block of CSS. */
function readBlock(block) {
  const tokens = {};
  for (const m of block.matchAll(/--([\w-]+)\s*:\s*([^;]+);/g)) {
    tokens[m[1]] = m[2].trim();
  }
  return tokens;
}

/** Return the interior of the `{ ... }` block whose `{` is at or after `from`. */
function readBraced(css, from) {
  const open = css.indexOf("{", from);
  if (open < 0) return null;
  let depth = 1;
  for (let i = open + 1; i < css.length; i++) {
    if (css[i] === "/" && css[i + 1] === "*") {
      const end = css.indexOf("*/", i + 2);
      if (end < 0) break;
      i = end + 1;
      continue;
    }
    if (css[i] === "{") depth++;
    else if (css[i] === "}" && --depth === 0) {
      return css.slice(open + 1, i);
    }
  }
  return null;
}

/** Pull `--name: value;` out of the :root blocks, one per theme. */
function extractTokens(css) {
  const lightStart = css.search(/(?:^|\n):root\s*\{/);
  const lightBlock = lightStart >= 0 ? readBraced(css, lightStart) : null;
  if (lightBlock === null) {
    console.error(`! could not locate the light :root block in ${SHEET}`);
    process.exit(2);
  }

  let darkBlock = null;
  for (const m of css.matchAll(/@media\s*\(\s*prefers-color-scheme\s*:\s*dark\s*\)/g)) {
    const mediaBody = readBraced(css, m.index);
    if (!mediaBody) continue;
    const rootAt = mediaBody.search(/(?:^|\n)\s*:root\s*\{/);
    if (rootAt >= 0) {
      const candidate = readBraced(mediaBody, rootAt);
      if (candidate && /--bg\s*:/.test(candidate)) {
        darkBlock = candidate;
        break;
      }
    }
  }
  if (darkBlock === null) {
    console.error(`! could not locate the dark :root block in ${SHEET}`);
    process.exit(2);
  }

  const lightTokens = readBlock(lightBlock);
  const blocks = {
    light: lightTokens,
    dark: { ...lightTokens, ...readBlock(darkBlock) },
  };

  // Resolve light-dark(a, b) and nested var() references into two themes.
  const resolve = (value, theme) =>
    value.replace(
      /light-dark\(\s*([^,()]+)\s*,\s*([^()]+)\s*\)/g,
      (_, light, dark) => (theme === "light" ? light : dark).trim(),
    );

  const themes = { light: {}, dark: {} };
  for (const theme of ["light", "dark"]) {
    const source = blocks[theme];
    for (const [name, raw] of Object.entries(source)) {
      let value = resolve(raw, theme);
      for (let i = 0; i < 4; i++) {
        const next = value.replace(/var\(--([\w-]+)\)/g, (whole, ref) => {
          return resolve(source[ref] ?? whole, theme);
        });
        if (next === value) break;
        value = next;
      }
      themes[theme][name] = value.trim();
    }
  }

  return themes;
}

function hexToRgb(hex) {
  let h = hex.trim().slice(1);
  if (h.length === 3) h = [...h].map((c) => c + c).join("");
  const n = parseInt(h, 16);
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
}

function luminance(hex) {
  const { r, g, b } = hexToRgb(hex);
  const channel = (c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function contrast(a, b) {
  const [l1, l2] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (l1 + 0.05) / (l2 + 0.05);
}

/** [foreground, background, required ratio (WCAG AAA 7:1), label] */
const PAIRS = [
  ["text", "bg", 7.0, "body text"],
  ["text", "surface", 7.0, "text on raised surface"],
  ["text-muted", "bg", 7.0, "muted text"],
  ["text-muted", "surface", 7.0, "muted text on surface"],
  ["text-muted", "surface-sunken", 7.0, "muted text on sunken"],
  ["text-faint", "bg", 7.0, "faint text (CiTO labels)"],
  ["link", "bg", 7.0, "link"],
  ["link", "surface", 7.0, "link on surface"],
  ["link-visited", "bg", 7.0, "visited link"],
  ["brand-ink", "brand", 7.0, "button text"],
  ["text", "code-bg", 7.0, "text on code background"],
  ["border-strong", "bg", 7.0, "tag border + year rule"],
  ["focus", "bg", 7.0, "focus ring"],
  ["focus", "surface", 7.0, "focus ring on surface"],
  // The topic pills and the selected theme button, both of which paint text on
  // a brand or sunken ground.
  ["brand", "brand-soft", 7.0, "topic pill on brand-soft (hover)"],
  ["text-faint", "surface-sunken", 7.0, "topic count on sunken"],
  // A registry value (`.identifier`) inherits its colour from its link, so it
  // is the link pair on each ground it appears over.
  ["link", "brand-soft", 7.0, "identifier link on brand-soft"],
];

const css = readFileSync(SHEET, "utf-8");
const themes = extractTokens(css);

let failures = 0;
let unresolved = 0;
let checks = 0;

for (const theme of ["light", "dark"]) {
  const t = themes[theme];
  console.log(`\n${theme} scheme`);
  for (const [fg, bg, required, label] of PAIRS) {
    if (
      !/^#(?:[0-9a-f]{3}|[0-9a-f]{6})$/i.test(t[fg] ?? "") ||
      !/^#(?:[0-9a-f]{3}|[0-9a-f]{6})$/i.test(t[bg] ?? "")
    ) {
      console.log(`  ?  ${label}: unresolved (${fg}=${t[fg]}, ${bg}=${t[bg]})`);
      unresolved++;
      continue;
    }
    const ratio = contrast(t[fg], t[bg]);
    checks++;
    const pass = ratio >= required;
    if (!pass) failures++;
    const grade =
      ratio >= 7
        ? "AAA"
        : ratio >= 4.5
          ? "AA"
          : ratio >= 3
            ? "AA-large"
            : "FAIL";
    console.log(
      `  ${pass ? "ok " : "FAIL"}  ${ratio.toFixed(2).padStart(5)}:1 ` +
        `(need ${required})  ${label} — ${t[fg]} on ${t[bg]} [${grade}]`,
    );
  }
}

console.log(
  `\n${checks - failures}/${checks} checks passed, ${unresolved} unresolved`,
);
// An unresolved token is a defect in the palette, not a WCAG failure: the pair
// was never actually tested, so counting it as a failure made the summary below
// the "N/0" line read a negative number of failures.
process.exit(failures || unresolved ? 1 : 0);
