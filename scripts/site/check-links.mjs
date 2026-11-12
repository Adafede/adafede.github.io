/**
 * Crawls a built site and reports internal links that resolve to nothing.
 *
 * Static output makes this cheap to check exactly: there is no server behaviour
 * to model, so a link either matches a file in the tree or it is broken. That
 * covers the failure mode that actually happens during a content migration —
 * a template pointing at a page that was renamed or dropped.
 *
 * Only root-relative links are checked. External URLs are not fetched: that
 * would make the check slow and flaky, and it would report other people's
 * outages rather than our bugs.
 *
 * Run: node scripts/site/check-links.mjs _eleventy_site
 */
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { htmlFiles, removeComments, removeScriptAndStyle } from "./html.mjs";

const roots = process.argv.slice(2);
if (!roots.length) {
  console.error("usage: check-links.mjs <dir> [dir...]");
  process.exit(2);
}

/** Schemes and forms that are not our problem to resolve. */
const EXTERNAL = /^(?:[a-z][a-z0-9+.-]*:|\/\/)/i;

const hasExtension = (p) => /\.[a-z0-9]+$/i.test(p);

function collectIds(html) {
  const ids = new Set();
  for (const m of html.matchAll(/\b(?:id|name)="([^"]+)"/gi)) {
    ids.add(m[1]);
  }
  return ids;
}

function* extractTargets(html) {
  for (const match of html.matchAll(/\b(?:href|src)="([^"]+)"/gi)) {
    yield match[1];
  }
  for (const match of html.matchAll(/\b(?:srcset|imagesrcset)="([^"]+)"/gi)) {
    for (const candidate of match[1].split(",")) {
      const url = candidate.trim().split(/\s+/)[0];
      if (url) yield url;
    }
  }
}

let totalDead = 0;

for (const rawRoot of roots) {
  const root = rawRoot.replace(/\/+$/, "");
  const pages = htmlFiles(root);
  const pageIds = new Map();
  for (const page of pages) {
    const rel = page.slice(root.length);
    const cleaned = removeComments(
      removeScriptAndStyle(readFileSync(page, "utf-8")),
    );
    pageIds.set(rel, { html: cleaned, ids: collectIds(cleaned) });
  }
  const dead = new Map();

  for (const [rel, { html }] of pageIds) {
    const from = rel || "/";
    for (const href of extractTargets(html)) {
      if (EXTERNAL.test(href)) continue;

      let resolved;
      try {
        resolved = new URL(href, `https://site.local${from}`);
      } catch {
        if (!dead.has(from)) dead.set(from, new Set());
        dead.get(from).add(href);
        continue;
      }

      let target = decodeURIComponent(resolved.pathname);
      if (target.endsWith("/")) target += "index.html";
      else if (!hasExtension(target)) {
        target = existsSync(join(root, target, "index.html"))
          ? `${target}/index.html`
          : `${target}.html`;
      }

      const fileExists =
        pageIds.has(target) || existsSync(join(root, target));
      if (!fileExists) {
        if (!dead.has(from)) dead.set(from, new Set());
        dead.get(from).add(href);
        continue;
      }

      const fragment = resolved.hash ? decodeURIComponent(resolved.hash.slice(1)) : "";
      if (fragment && pageIds.has(target)) {
        const ids = pageIds.get(target).ids;
        if (!ids.has(fragment)) {
          if (!dead.has(from)) dead.set(from, new Set());
          dead.get(from).add(href);
        }
      }
    }
  }

  const broken = [...dead.entries()].reduce(
    (n, [, links]) => n + links.size,
    0,
  );
  totalDead += broken;
  console.log(
    `${rawRoot}: ${pages.length} pages, ${broken} dead internal link(s)`,
  );
  for (const [from, links] of dead) {
    console.log(`  ${from} -> ${[...links].slice(0, 5).join(", ")}`);
  }
}

process.exit(totalDead ? 1 : 0);
