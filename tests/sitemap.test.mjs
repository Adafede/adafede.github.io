import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const contentDir = join(here, '..', 'src', 'content');
const available = existsSync(contentDir);

test('sitemap contains every content page exactly once', { skip: !available }, async () => {
  const { default: sitemap } = await import('../src/eleventy/_data/sitemap.js');
  const { default: buildContent } = await import('../src/eleventy/_data/sitecontent.js');
  const content = buildContent();

  const locs = sitemap.map((u) => u.loc);

  const dupes = locs.filter((loc, i) => locs.indexOf(loc) !== i);
  assert.equal(dupes.length, 0, `duplicate locs: ${dupes.join(', ')}`);

  const expected = [];
  for (const fn of ['posts', 'articles', 'talks', 'teaching', 'varia']) {
    for (const item of content[fn]()) {
      expected.push(item.url);
    }
  }
  expected.push('/', '/posts.html', '/articles.html', '/talks.html', '/teaching.html', '/varia.html', '/cv.html');

  for (const url of expected) {
    assert.ok(locs.includes(url), `missing ${url} from sitemap`);
  }

  assert.ok(!locs.includes('/404.html'), '404 must not be in sitemap');
  assert.ok(!locs.includes('/blog.html'), 'redirect page must not be in sitemap');
  assert.ok(!locs.includes('/rss.html'), 'redirect page must not be in sitemap');
});
