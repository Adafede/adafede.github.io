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
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

import { htmlFiles } from './html.mjs';

const roots = process.argv.slice(2);
if (!roots.length) {
  console.error('usage: check-links.mjs <dir> [dir...]');
  process.exit(2);
}

/** Schemes and forms that are not our problem to resolve. */
const EXTERNAL = /^(?:[a-z][a-z0-9+.-]*:|\/\/|#)/i;

const hasExtension = (p) => /\.[a-z0-9]+$/i.test(p);

let totalDead = 0;

for (const root of roots) {
  const pages = htmlFiles(root);
  const known = new Set(pages.map((p) => p.slice(root.length)));
  const dead = new Map();

  for (const page of pages) {
    const html = readFileSync(page, 'utf-8');
    for (const match of html.matchAll(/(?:href|src)="([^"]+)"/g)) {
      const href = match[1];
      if (EXTERNAL.test(href)) continue;

      // Fragments and query strings address a resource we have already resolved.
      const path = href.split('#')[0].split('?')[0];
      if (!path.startsWith('/')) continue;

      let target = path;
      if (target.endsWith('/')) target += 'index.html';
      else if (!hasExtension(target)) {
        // Extensionless URLs are served by directory index or by the server
        // stripping .html; either way an index document satisfies them.
        target = existsSync(join(root, target, 'index.html')) ? `${target}/index.html` : `${target}.html`;
      }

      if (known.has(target) || existsSync(join(root, target))) continue;

      const from = page.slice(root.length) || '/';
      if (!dead.has(from)) dead.set(from, new Set());
      dead.get(from).add(href);
    }
  }

  const broken = [...dead.entries()].reduce((n, [, links]) => n + links.size, 0);
  totalDead += broken;
  console.log(`${root}: ${pages.length} pages, ${broken} dead internal link(s)`);
  for (const [from, links] of dead) {
    console.log(`  ${from} -> ${[...links].slice(0, 5).join(', ')}`);
  }
}

process.exit(totalDead ? 1 : 0);
