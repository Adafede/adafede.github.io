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

/** Pull `--name: value;` out of the :root blocks, one per theme. */
function extractTokens(css) {
  // The dark palette is a second :root inside
  // `@media (prefers-color-scheme: dark)` rather than a light-dark() override,
  // so reading only the first :root meant the "dark scheme" pass silently
  // re-checked the light values and the dark theme was never actually tested.
  // The first `prefers-color-scheme: dark` block only restyles code blocks, so
  // match the one whose :root actually declares the palette.
  const darkAt = css.lastIndexOf("@media (prefers-color-scheme: dark)");
  const darkRoot = css.indexOf(":root {", darkAt);
  const lightStart = css.indexOf(":root {");
  const lightEnd = css.indexOf("\n}", lightStart);
  if (lightStart < 0 || lightEnd < 0) {
    console.error(`! could not locate the light :root block in ${SHEET}`);
    process.exit(2);
  }
  const darkEnd = css.indexOf("\n}", darkRoot);
  if (darkRoot < 0 || darkEnd < 0) {
    console.error(`! could not locate the dark :root block in ${SHEET}`);
    process.exit(2);
  }
  const blocks = {
    light: readBlock(css.slice(lightStart, lightEnd)),
    dark: readBlock(css.slice(darkRoot, darkEnd)),
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
      // One pass of var() substitution is enough for this palette.
      for (let i = 0; i < 3; i++) {
        const next = value.replace(/var\(--([\w-]+)\)/g, (whole, ref) => {
          return source[ref] ?? whole;
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
  let h = hex.trim().replace("#", "");
  if (h.length === 3 || h.length === 4) h = [...h].map((c) => c + c).join("");
  if (h.length === 8) h = h.slice(0, 6);
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

/** [foreground, background, required ratio, label] */
const PAIRS = [
  ["text", "bg", 4.5, "body text"],
  ["text", "surface", 4.5, "text on raised surface"],
  ["text-muted", "bg", 4.5, "muted text"],
  ["text-muted", "surface", 4.5, "muted text on surface"],
  ["text-muted", "surface-sunken", 4.5, "muted text on sunken"],
  ["text-faint", "bg", 4.5, "faint text (CiTO labels)"],
  ["link", "bg", 4.5, "link"],
  ["link", "surface", 4.5, "link on surface"],
  ["link-visited", "bg", 4.5, "visited link"],
  ["brand-ink", "brand", 4.5, "button text"],
  ["text", "code-bg", 4.5, "text on code background"],
  ["border-strong", "bg", 3.0, "tag border + year rule"],
  ["focus", "bg", 3.0, "focus ring"],
  ["focus", "surface", 3.0, "focus ring on surface"],
  // The topic pills and the selected theme button, both of which paint text on
  // a brand or sunken ground.
  ["brand", "brand-soft", 4.5, "topic pill on brand-soft (hover)"],
  ["text-faint", "surface-sunken", 4.5, "topic count on sunken"],
  // A registry value (`.identifier`) inherits its colour from its link, so it
  // is the link pair on each ground it appears over.
  ["link", "brand-soft", 4.5, "identifier link on brand-soft"],
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
      !/^#[0-9a-f]{3,8}$/i.test(t[fg] ?? "") ||
      !/^#[0-9a-f]{3,8}$/i.test(t[bg] ?? "")
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
