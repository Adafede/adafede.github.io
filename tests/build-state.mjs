// Shared by the tests that read generated output (src/content/, _eleventy_site/)
// instead of fixtures. Without this they passed against whatever was on disk,
// including output built before the change under test.
import { existsSync, readdirSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

const CONTENT_SOURCES = [
  "posts",
  "talks",
  "teaching",
  "varia",
  "articles",
  "cv",
  "cv.qmd",
  "_includes/entities",
  "scripts/site/migrate_posts.py",
];

const SITE_SOURCES = [
  ...CONTENT_SOURCES,
  "src/eleventy",
  "src/lib",
  "src/styles",
  "eleventy.config.mjs",
];

function newestMtime(path) {
  if (!existsSync(path)) return 0;
  const stat = statSync(path);
  if (!stat.isDirectory()) return stat.mtimeMs;
  let newest = 0;
  for (const entry of readdirSync(path)) {
    newest = Math.max(newest, newestMtime(join(path, entry)));
  }
  return newest;
}

function skipReason(marker, sources, command) {
  // CI builds from a clean checkout right before these tests, and a skip there
  // would hide a missing build; let the test fail instead.
  if (process.env.CI) return false;
  const markerPath = join(ROOT, marker);
  if (!existsSync(markerPath)) return `needs ${marker} (${command})`;
  const built = statSync(markerPath).mtimeMs;
  const stale = sources.find((source) => newestMtime(join(ROOT, source)) > built);
  return stale ? `${marker} is older than ${stale} (${command})` : false;
}

/** `skip` value for a test that reads src/content/. */
export const contentSkip = () =>
  skipReason("src/content/affiliations.json", CONTENT_SOURCES, "bun run sync:content");

/** `skip` value for a test that reads _eleventy_site/. */
export const siteSkip = () =>
  skipReason(
    "_eleventy_site/index.html",
    SITE_SOURCES,
    "bun run sync:content && bun run build:eleventy",
  );
