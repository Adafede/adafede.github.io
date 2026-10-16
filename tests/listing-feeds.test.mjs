import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const contentDir = join(here, "..", "src", "content");
const available = existsSync(contentDir);

async function rssFeed() {
  const { default: listingFeeds } =
    await import("../src/eleventy/_data/listingFeeds.js");
  return listingFeeds().find((feed) => feed.slug === "rss");
}

test(
  "rss feed is capped to the most recent items from every listing, not the first 20 articles",
  { skip: !available },
  async () => {
    const rss = await rssFeed();
    const capped = rss.items().slice(0, rss.limit);

    assert.ok(
      capped.length === rss.limit,
      `expected ${rss.limit} items, got ${capped.length}`,
    );

    const byListing = new Map();
    for (const item of capped) {
      const listing = item.url.split("/")[1] || "(root)";
      byListing.set(listing, (byListing.get(listing) || 0) + 1);
    }

    assert.ok(
      byListing.size >= 3,
      `expected items from at least 3 listings, got ${[...byListing].join(", ")}`,
    );
    assert.ok(byListing.has("posts"), "expected posts in the capped feed");
    assert.ok(byListing.has("talks"), "expected talks in the capped feed");

    for (const item of capped) {
      assert.ok(rss.date(item), `item ${item.url} has no date`);
    }
  },
);

test(
  "rss feed is ordered newest-first with undated items last",
  { skip: !available },
  async () => {
    const rss = await rssFeed();
    const items = rss.items();

    const stamps = items.map((item) => {
      const when = rss.date(item);
      if (!when) return 0;
      const time = new Date(when).getTime();
      return Number.isNaN(time) ? 0 : time;
    });

    for (let i = 1; i < stamps.length; i++) {
      assert.ok(
        stamps[i] <= stamps[i - 1],
        `item ${i} is newer than item ${i - 1} (${items[i].url})`,
      );
    }

    const firstUndated = stamps.findIndex((s) => s === 0);
    if (firstUndated !== -1) {
      assert.ok(
        stamps.slice(firstUndated).every((s) => s === 0),
        "undated items must sort last",
      );
    }
  },
);
