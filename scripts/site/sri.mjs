/**
 * Derives the Subresource Integrity hash of the self-hosted theme script and
 * stamps it into every place the site declares one.
 *
 * theme-form.js is a build input (src/eleventy/static/theme-form.js), so its
 * hash is a function of the source tree. Hand-syncing it across the integrity
 * attribute, the CSP meta tag and _headers meant an edit to the script could
 * silently ship a page whose CSP blocks it. The Eleventy side reads the helper
 * below at config time (see eleventy.config.mjs); the _headers side is written
 * here, because _headers is deployed as a file rather than rendered.
 *
 * The Simple Analytics hash stays hard-coded: it is a remote script fetched
 * from a versionless URL, so there is no local file to derive it from.
 *
 * Run: node scripts/site/sri.mjs
 */
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

/** Local scripts whose hash the build owns, mapped to their served path. */
export const LOCAL_SCRIPTS = {
  "themeForm": "src/eleventy/static/theme-form.js",
};

/** Placeholder in _headers that stands for the theme-form hash. */
export const TOKEN = "__THEME_FORM_SRI__";

/**
 * Returns the SRI token for a local script, e.g. `sha256-<base64>`.
 *
 * @param {keyof typeof LOCAL_SCRIPTS} name Key in LOCAL_SCRIPTS.
 * @param {string} [algorithm] Digest name; defaults to sha256 to match the
 *   algorithm browsers apply for classic (non-module) scripts.
 * @returns {string} The full SRI token.
 * @throws {Error} If the script is missing or not in LOCAL_SCRIPTS.
 */
export function sriFor(name, algorithm = "sha256") {
  const rel = LOCAL_SCRIPTS[name];
  if (!rel) throw new Error(`unknown script ${name}`);
  const file = join(ROOT, rel);
  if (!existsSync(file)) throw new Error(`missing script ${rel}`);
  const digest = createHash(algorithm).update(readFileSync(file)).digest("base64");
  return `${algorithm}-${digest}`;
}

/**
 * Writes public/_headers from the root template with the hash token resolved.
 *
 * A missing template is not fatal: _headers documents a Netlify deployment that
 * only some forks run, and a branch without it should still build.
 */
function stageHeaders() {
  const template = join(ROOT, "_headers");
  if (!existsSync(template)) return;
  const out = join(ROOT, "public", "_headers");
  const text = readFileSync(template, "utf8");
  if (!text.includes(TOKEN)) return;
  mkdirSync(dirname(out), { recursive: true });
  writeFileSync(out, text.replaceAll(TOKEN, sriFor("themeForm")));
}

if (import.meta.url === `file://${process.argv[1]}`) {
  stageHeaders();
  console.log(`  + _headers staged (theme-form.js ${sriFor("themeForm")})`);
}
